#!/usr/bin/env python3
"""Run the existing Mac Ollama and Personal Codex with authenticated loopback services."""

from __future__ import annotations

import argparse
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import shutil
import secrets
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import network_policy

BACKEND_PORT = 8787
OLLAMA_PORT = 11434
APP_BINARY = Path("Contents/MacOS/personal-codex")
PREVIOUS_APP = ROOT / "data/offline-app/Personal Codex.app"
AUTONOMOUS_APP = ROOT / "data/autonomous-app/Personal Codex.app"
FULL_TASK_APP = ROOT / "data/full-task-app/Personal Codex.app"
OBSERVABILITY_APP = ROOT / "data/observability-app/Personal Codex.app"
DOCUMENTS_APP = ROOT / "data/document-search-app/Personal Codex.app"
MAC_ACTIONS_APP = ROOT / "data/mac-actions-app/Personal Codex.app"
CANDIDATE_APP = ROOT / "desktop/src-tauri/target/release/bundle/macos/Personal Codex.app"
DEFAULT_APP = next((path for path in (CANDIDATE_APP, MAC_ACTIONS_APP, DOCUMENTS_APP, OBSERVABILITY_APP, FULL_TASK_APP, AUTONOMOUS_APP) if (path / APP_BINARY).is_file()), PREVIOUS_APP)


def private_dir(path: Path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Offline data directory must be a real, owner-only directory (mode 0700)")


def get_json(port, path):
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        if response.status != 200:
            raise OSError(f"Readiness check for port {port} returned HTTP {response.status}")
        return json.loads(response.read(200_000))
    finally:
        connection.close()


def wait_ready(process, port, route, timeout=15):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Service on port {port} exited during startup")
        try:
            return get_json(port, route)
        except (OSError, ValueError) as error:
            last_error = error
            time.sleep(0.2)
    raise RuntimeError(f"Service on port {port} did not become ready within {timeout}s: {last_error}")


def require_free_ports(*, reuse_ollama=False):
    for port in ((BACKEND_PORT,) if reuse_ollama else (OLLAMA_PORT, BACKEND_PORT)):
        for address in ("127.0.0.1", "::1"):
            try:
                with socket.create_connection((address, port), timeout=1):
                    pass
            except ConnectionRefusedError:
                continue
            raise ValueError(f"Port {port} is in use. Quit the existing Ollama app or Personal Codex backend and try again.")


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-ollama", action="store_true", help="use the existing loopback Ollama without starting, stopping or reconfiguring it")
    parser.add_argument("--model", choices=network_policy.OFFLINE_MODELS,
                        help="require this installed model (defaults to the first supported model in the local cache)")
    parser.add_argument("--project-root", type=Path, help="existing directory dedicated to the hackathon repositories")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/offline")
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--backend-only", action="store_true", help="keep the loopback services running without launching the UI")
    args = parser.parse_args()

    if sys.platform != "darwin":
        parser.error("This launcher requires macOS")
    app = args.app.expanduser().resolve() / APP_BINARY
    if not args.backend_only and not os.access(app, os.X_OK):
        parser.error("The built Personal Codex app was not found. Use --app with its full .app path.")
    ollama = shutil.which("ollama")
    if not ollama:
        parser.error("The installed Ollama command could not be found")

    data = args.data_dir.expanduser().absolute()
    private_dir(data)
    data = data.resolve()
    if args.project_root:
        projects = args.project_root.expanduser().resolve(strict=True)
        if not projects.is_dir() or projects == data or projects in data.parents or data in projects.parents:
            parser.error("Use a directory dedicated to the hackathon repositories, outside the private offline data directory")
    else:
        projects = data / "projects"
        private_dir(projects)
    require_free_ports(reuse_ollama=args.reuse_ollama)

    # Reuse the existing token creation path. Neither the token nor its contents go in an argument,
    # subprocess environment, browser storage, or this launcher's output.
    token = data / "owner.token"
    if not os.path.lexists(token):
        subprocess.run([sys.executable, str(ROOT / "scripts/private_backend.py"), "--create-token", str(token)], check=True)
    session = Path(tempfile.mkdtemp(prefix="session-", dir=data))
    print(f"Offline service logs: {session}", flush=True)

    # Keep the normal user cache and project toolchain. Drop inherited provider, proxy and
    # deployment environment settings for these managed processes. Retain existing CA
    # locations so verified HTTPS downloads use the same trust as the launcher.
    env = {key: os.environ[key] for key in ("HOME", "PATH", "TMPDIR", "USER", "LOGNAME", "LANG", "SSL_CERT_FILE", "SSL_CERT_DIR") if key in os.environ}
    native_grant = secrets.token_urlsafe(32)
    processes = []
    try:
        daemon = None
        if args.reuse_ollama:
            get_json(OLLAMA_PORT, "/api/version")
            print("Using the existing loopback Ollama; its lifecycle remains under your control.", flush=True)
        else:
            with (session / "ollama.log").open("xb") as log:
                daemon = subprocess.Popen(
                    [ollama, "serve"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                    env={**env, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_NO_CLOUD": "1",
                         "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1",
                         "OLLAMA_CONTEXT_LENGTH": "8192", "OLLAMA_KEEP_ALIVE": "3m"},
                )
            processes.append(daemon)
            wait_ready(daemon, OLLAMA_PORT, "/api/version")
        names = {model["name"] for model in get_json(OLLAMA_PORT, "/api/tags")["models"]}
        if args.model and args.model not in names:
            raise ValueError(f"{args.model} is missing from the local Ollama cache")
        model = args.model or next((name for name in network_policy.OFFLINE_MODELS if name in names), None)
        if not model:
            supported = ", ".join(network_policy.OFFLINE_MODELS)
            raise ValueError(f"No supported model is installed in the local Ollama cache. Supported models: {supported}")
        with (session / "backend.log").open("xb") as log:
            backend = subprocess.Popen(
                [sys.executable, "-u", str(ROOT / "app/server.py")], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                env={**env, "PERSONAL_CODEX_INFERENCE_POLICY": "offline", "PERSONAL_CODEX_HOST": "127.0.0.1",
                     "PERSONAL_CODEX_DATA": str(data), "PERSONAL_CODEX_TOKEN_FILE": str(token),
                     "PERSONAL_CODEX_PROJECT_ROOTS": str(projects), "PERSONAL_CODEX_OFFLINE_MODEL": model,
                     "PERSONAL_CODEX_INSTALLED_OFFLINE_MODELS": ",".join(name for name in network_policy.OFFLINE_MODELS if name in names),
                     "PERSONAL_CODEX_MAX_CONTEXT_BYTES": "12000", "PERSONAL_CODEX_NATIVE_GRANT": native_grant},
            )
        processes.append(backend)
        wait_ready(backend, BACKEND_PORT, "/api/health", timeout=30)

        print(f"Personal Codex offline at http://127.0.0.1:8787, default {model}", flush=True)
        print(f"Project root: {projects}", flush=True)
        if args.backend_only:
            while (daemon is None or daemon.poll() is None) and backend.poll() is None:
                time.sleep(0.5)
            raise RuntimeError("A managed offline service exited")
        gui = subprocess.Popen([str(app)], cwd=app.parent, env={**env, "PERSONAL_CODEX_OFFLINE_TOKEN_FILE": str(token),
                                                          "PERSONAL_CODEX_NATIVE_GRANT": native_grant})
        processes.append(gui)
        while gui.poll() is None:
            if (daemon is not None and daemon.poll() is not None) or backend.poll() is not None:
                raise RuntimeError("A managed offline service exited")
            time.sleep(0.5)
        return gui.returncode
    finally:
        for process in reversed(processes):
            stop(process)


if __name__ == "__main__":
    # SIGINT and SIGTERM both unwind the launcher so its own children stop cleanly.
    def terminate(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, ValueError, RuntimeError) as error:
        sys.exit(str(error))
