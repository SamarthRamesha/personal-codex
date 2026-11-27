#!/usr/bin/env python3
"""Exercise the production launcher with a scripted Ollama inventory on a disposable Mac runner."""

from http.client import HTTPConnection
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import offline_workstation as launcher


def catalog(token=None):
    connection = HTTPConnection("127.0.0.1", launcher.BACKEND_PORT, timeout=5)
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        connection.request("GET", "/api/providers", headers=headers)
        response = connection.getresponse()
        return response.status, json.load(response)
    finally:
        connection.close()


def main():
    if sys.platform != "darwin":
        raise SystemExit("Launcher acceptance requires macOS")
    launcher.require_free_ports()
    with tempfile.TemporaryDirectory(prefix="personal-codex-launcher-") as temporary:
        root = Path(temporary)
        fake = root / "ollama"
        fake.write_text(f"#!{sys.executable}\n" + """
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        routes = {
            "/api/version": {"version": "fixture"},
            "/api/tags": {"models": [{"name": "qwen2.5-coder:14b"}]},
        }
        value = routes.get(self.path)
        self.send_response(200 if value is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())

HTTPServer(("127.0.0.1", 11434), Fixture).serve_forever()
""")
        fake.chmod(0o700)
        profile = root / "profile"
        with (root / "launcher.log").open("w+b") as log:
            process = subprocess.Popen(
                [sys.executable, str(launcher.ROOT / "scripts/offline_workstation.py"),
                 "--backend-only", "--data-dir", str(profile)],
                env={**os.environ, "PATH": f"{root}{os.pathsep}{os.environ['PATH']}"},
                stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 35
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"Launcher exited during startup with status {process.returncode}")
                    try:
                        launcher.get_json(launcher.BACKEND_PORT, "/api/health")
                        break
                    except (OSError, ValueError) as error:
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Fixture backend did not become ready") from error
                        time.sleep(0.2)
                assert catalog()[0] == 401
                token = (profile / "owner.token").read_text().strip()
                status, providers = catalog(token)
                assert status == 200 and [row["model"] for row in providers] == ["qwen2.5-coder:14b"]
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=28)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                log.seek(0)
                output = log.read().decode(errors="replace")
                print(output, end="")
                if sys.exc_info()[0] is not None:
                    for path in sorted(profile.glob("session-*/*.log")):
                        output += f"\n{path.name}: {path.read_text(errors='replace')[-1200:]}"
                    print("::error title=Launcher fixture startup::" + output[-3500:].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A"))
        assert process.returncode == 130
        for port in (launcher.BACKEND_PORT, launcher.OLLAMA_PORT):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=2):
                    raise AssertionError(f"Owned listener on port {port} did not stop")
            except ConnectionRefusedError:
                pass
    print("Offline launcher started the private backend, selected the sole fixture model, and stopped both listeners.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"::error title=Offline launcher fixture::{type(error).__name__}: {error}")
        raise
