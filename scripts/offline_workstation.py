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
import sqlite3
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


def listening(port):
    """True when something answers on a loopback address for this port."""
    for address in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((address, port), timeout=1):
                return True
        except OSError:
            continue
    return False


def doctor(data, app, model=None, *, backend_only=False, reuse_ollama=False):
    """Read-only launch readiness. Starts no service and changes no permission."""
    checks = []

    def add(name, status, detail, remedy=""):
        checks.append({"check": name, "status": status, "detail": detail, "remedy": remedy})

    mac = sys.platform == "darwin"
    add("platform", "ok" if mac else "fail", f"host reports {sys.platform}" + (" (macOS)" if mac else ""),
        "" if mac else "Run the launcher on macOS 14 or later.")

    version = sys.version_info
    add("python", "ok" if version >= (3, 11) else "fail", f"Python {version.major}.{version.minor}.{version.micro}",
        "" if version >= (3, 11) else "Run the launcher with Python 3.11 or newer.")

    git = shutil.which("git")
    add("git", "ok" if git else "warn", git or "git is not on PATH",
        "" if git else "Install the Xcode command line tools; reviewed delivery commits through Git.")

    try:
        private_dir(data)
        add("data-directory", "ok", f"{data} is an owner-only directory", "")
    except (OSError, ValueError) as error:
        add("data-directory", "fail", str(error),
            "Choose a new --data-dir you own; never widen an existing profile's permissions.")

    try:
        free = shutil.disk_usage(data).free
        add("disk-space", "ok" if free >= 5 * 1024 ** 3 else "warn", f"{free / 1024 ** 3:.1f} GiB free at {data}",
            "" if free >= 5 * 1024 ** 3 else "Free disk space; model caches and task worktrees share this volume.")
    except OSError as error:
        add("disk-space", "warn", str(error), "")

    if not backend_only:
        binary = app / APP_BINARY
        if binary.is_file() and os.access(binary, os.X_OK):
            add("app-bundle", "ok", str(app), "")
        else:
            add("app-bundle", "fail", f"{binary} was not found",
                "Pass --app with the full path to Personal Codex.app, or launch with --backend-only.")

    ollama = shutil.which("ollama")
    add("ollama-command", "ok" if ollama else "fail", ollama or "the ollama command is not on PATH",
        "" if ollama else "Install Ollama and open it once so its models are in the local cache.")

    ollama_busy = listening(OLLAMA_PORT)
    model_port_blocked = ollama_busy and not reuse_ollama
    add("ollama-port", "fail" if model_port_blocked else "ok",
        f"port {OLLAMA_PORT} is {'in use' if ollama_busy else 'free'}",
        "Add --reuse-ollama to use the running Ollama, or quit it first." if model_port_blocked else "")
    if reuse_ollama and not ollama_busy:
        add("reuse-ollama", "fail", "--reuse-ollama was given but nothing is serving on port 11434",
            "Open Ollama first, or drop --reuse-ollama so the launcher starts it.")
    backend_busy = listening(BACKEND_PORT)
    add("backend-port", "fail" if backend_busy else "ok", f"port {BACKEND_PORT} is {'in use' if backend_busy else 'free'}",
        "Quit the process using port 8787; it is probably a previous backend." if backend_busy else "")

    installed = None
    read_error = None
    if ollama_busy:
        try:
            installed = [row["name"] for row in get_json(OLLAMA_PORT, "/api/tags")["models"]]
        except (OSError, ValueError, KeyError) as error:
            read_error = error
    if read_error is not None:
        add("installed-models", "warn", f"Ollama answered but its model list could not be read: {read_error}", "")
    elif installed is None:
        add("installed-models", "warn", "not checked; the launcher verifies the cache after starting Ollama", "")
    else:
        vetted = [name for name in network_policy.OFFLINE_MODELS if name in installed]
        chosen = model or (vetted[0] if vetted else None)
        if not installed:
            add("installed-models", "fail", "no models are installed in the local Ollama cache",
                "Run ollama pull qwen3.5:9b (or another model) first.")
        elif chosen is None:
            add("installed-models", "warn", f"no vetted model installed; installed: {', '.join(sorted(installed))}",
                "Pass --model with one of the installed tags.")
        elif chosen not in installed:
            add("installed-models", "fail", f"{chosen} is not installed; installed: {', '.join(sorted(installed))}",
                "Pass --model with an installed tag, or pull the model first.")
        else:
            vetted_model = chosen in network_policy.OFFLINE_MODELS
            add("installed-models", "ok" if vetted_model else "warn",
                f"selected {chosen}" + ("" if vetted_model else "; not on the vetted coding list"),
                "" if vetted_model else "Structured proposals may be less reliable with an unvetted model.")

    database = data / "personal_codex.db"
    if database.is_file():
        try:
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            try:
                result = connection.execute("PRAGMA integrity_check").fetchall()
            finally:
                connection.close()
            add("database", "ok" if result == [("ok",)] else "fail",
                f"{database} integrity_check {result}",
                "Keep the damaged profile for inspection and restore a verified snapshot to a new directory.")
        except sqlite3.Error as error:
            add("database", "fail", f"{database} could not be inspected: {error}",
                "Keep the profile for inspection and restore a verified snapshot to a new directory.")

    failures = [check["check"] for check in checks if check["status"] == "fail"]
    return {"ready": not failures, "checks": checks, "failures": failures,
            "warnings": [check["check"] for check in checks if check["status"] == "warn"]}


def print_doctor(report, *, as_json=False):
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for check in report["checks"]:
            print(f"[{check['status'].upper():4}] {check['check']}: {check['detail']}")
            if check["remedy"]:
                print(f"       {check['remedy']}")
        print(f"Ready to launch offline: {'yes' if report['ready'] else 'no'}")
    return 0 if report["ready"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-ollama", action="store_true", help="use the existing loopback Ollama without starting, stopping or reconfiguring it")
    parser.add_argument("--model", help="installed Ollama tag to use (defaults to the first vetted installed model)")
    parser.add_argument("--project-root", type=Path, help="existing directory dedicated to the hackathon repositories")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/offline")
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--backend-only", action="store_true", help="keep the loopback services running without launching the UI")
    parser.add_argument("--doctor", action="store_true", help="check launch readiness without starting a service")
    parser.add_argument("--json", action="store_true", help="print the --doctor report as JSON")
    args = parser.parse_args()
    if args.json and not args.doctor:
        parser.error("--json can only be used with --doctor")
    if args.model:
        try:
            network_policy.model_tag(args.model)
        except ValueError as error:
            parser.error(str(error))
    if args.doctor:
        return print_doctor(doctor(args.data_dir.expanduser().absolute(),
                                   (args.app or DEFAULT_APP).expanduser().absolute(), args.model,
                                   backend_only=args.backend_only, reuse_ollama=args.reuse_ollama),
                            as_json=args.json)

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
        names = {row["name"] for row in get_json(OLLAMA_PORT, "/api/tags")["models"]}
        if args.model and args.model not in names:
            installed = ", ".join(sorted(names)) or "none"
            raise ValueError(f"{args.model} is not installed in the local Ollama cache. Installed models: {installed}")
        vetted_installed = [name for name in network_policy.OFFLINE_MODELS if name in names]
        model = args.model or (vetted_installed[0] if vetted_installed else None)
        if not model:
            installed = ", ".join(sorted(names)) or "none"
            supported = ", ".join(network_policy.OFFLINE_MODELS)
            raise ValueError(f"No vetted model is installed. Installed models: {installed}. Vetted models: {supported}. "
                             "Pass --model with an installed tag to use another model.")
        if model not in network_policy.OFFLINE_MODELS:
            print(f"Using {model}, which is not on the vetted coding list; structured proposals may be less reliable.", flush=True)
        inventory = [name for name in dict.fromkeys((model, *network_policy.OFFLINE_MODELS)) if name in names]
        with (session / "backend.log").open("xb") as log:
            backend = subprocess.Popen(
                [sys.executable, "-u", str(ROOT / "app/server.py")], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                env={**env, "PERSONAL_CODEX_INFERENCE_POLICY": "offline", "PERSONAL_CODEX_HOST": "127.0.0.1",
                     "PERSONAL_CODEX_DATA": str(data), "PERSONAL_CODEX_TOKEN_FILE": str(token),
                     "PERSONAL_CODEX_PROJECT_ROOTS": str(projects), "PERSONAL_CODEX_OFFLINE_MODEL": model,
                     "PERSONAL_CODEX_INSTALLED_OFFLINE_MODELS": ",".join(inventory),
                     "PERSONAL_CODEX_OFFLINE_MODELS": ",".join(name for name in inventory if name not in network_policy.OFFLINE_MODELS),
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
