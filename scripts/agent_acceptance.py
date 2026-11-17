#!/usr/bin/env python3
"""Authenticated disposable local coding scenario. Requires Mac sandbox execution."""
from argparse import ArgumentParser
from http.client import HTTPConnection
from pathlib import Path
import json
import os
import secrets
import shutil
import sys
import textwrap
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--scenario", choices=("create", "repair", "pdf", "ocr", "typescript", "react"), default="create")
    parser.add_argument("--cancel-resume", action="store_true", help="Stop the first fixture model round and explicitly resume")
    parser.add_argument("--live", action="store_true", help="Use the already running local Ollama model")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    data = output / "state"
    places = output / "chosen-parent"
    places.mkdir(mode=0o700)
    os.environ.update(PERSONAL_CODEX_DATA=str(data), PERSONAL_CODEX_PROJECT_ROOTS=str(output / "allowed-managed"),
                      PERSONAL_CODEX_INFERENCE_POLICY="offline", PERSONAL_CODEX_NATIVE_GRANT=secrets.token_urlsafe(32))
    from app import local_runner, network_policy, security, server
    token = secrets.token_urlsafe(32)
    server.AUTH = security.OwnerAuth(token)
    server.STORE = server.Store()
    server.seed_offline_providers()
    results = []
    entered = threading.Event()
    release = threading.Event()
    if not args.live:
        def fixture(request):
            if args.cancel_resume and not entered.is_set():
                entered.set()
                release.wait(5)
            if args.scenario == "typescript":
                if "ERR_MODULE_NOT_FOUND" in request["prompt"]:
                    ops = [{"tool": "apply_patch", "path": "test_math.ts", "old_text": "./math.js", "new_text": "./math.ts"}]
                    return {"text": json.dumps({"summary": "Fix generated test import", "status": "continue", "operations": ops})}
                ops = [
                    {"tool": "create_file", "path": "math.ts", "content": "export const twice = (n: number) => n * 2;\n"},
                    {"tool": "create_file", "path": "test_math.ts", "content": "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport { twice } from './math.js';\ntest('twice', () => assert.equal(twice(3), 6));\n"},
                    {"tool": "create_file", "path": "package.json",
                     "content": json.dumps({"type": "module", "scripts": {"test": "node --test test_math.ts"}})},
                ]
                return {"text": json.dumps({"summary": "TypeScript fixture", "status": "continue", "operations": ops})}
            if "def add(a, b):" not in request["prompt"]:
                ops = [{"tool": "create_file", "path": "calculator.py", "content": "def add(a, b):\n    return a - b\n"},
                       {"tool": "create_file", "path": "tests/test_calculator.py",
                        "content": "import unittest\nfrom calculator import add\nclass TestAdd(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"}]
            else:
                assert "AssertionError" in request["prompt"]
                ops = [{"tool": "apply_patch", "path": "calculator.py", "old_text": "return a - b", "new_text": "return a + b"}]
            return {"text": json.dumps({"summary": "Addition fixture round", "status": "continue", "operations": ops})}
        server.PROVIDER_TRANSPORT = fixture

    control = server.runtime.ControlServer(("127.0.0.1", 0), server.App)
    thread = threading.Thread(target=control.serve_forever, daemon=True)
    thread.start()

    def call(path, payload=None, *, expected=200, grant=False):
        client = HTTPConnection("127.0.0.1", control.server_port, timeout=30)
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
        if grant:
            headers["X-Personal-Codex-Native"] = os.environ["PERSONAL_CODEX_NATIVE_GRANT"]
        try:
            client.request("GET" if payload is None else "POST", path, None if payload is None else json.dumps(payload), headers)
            response = client.getresponse()
            value = json.load(response)
            if response.status != expected:
                raise RuntimeError(f"{path}: HTTP {response.status}: {value.get('error')}")
            return value
        finally:
            client.close()

    started = time.monotonic()
    evidence = {"live": args.live, "model": args.model, "scenario": args.scenario, "checks": results}
    try:
        sandbox_root = output / "sandbox"
        sandbox_root.mkdir()
        outside = output / "outside"
        outside.mkdir()
        target = outside / "external.txt"
        target.write_text("outside")
        (sandbox_root / "visible.txt").write_text("workspace")
        (sandbox_root / "alias.txt").symlink_to(target)
        probe = local_runner.verify_boundary(sandbox_root, target, sys.executable)
        if probe.returncode:
            raise RuntimeError(f"macOS process-boundary checks failed ({probe.returncode}): {probe.stderr[-700:]}")
        results.append("sandbox denies external file data, outside listing/writes, symlink escapes and IPv4/IPv6")
        stat = places.stat()
        native = {"parent": str(places), "name": "Addition Fixture", "device": stat.st_dev, "inode": stat.st_ino}
        call("/api/native/projects", native, expected=403)
        project = call("/api/native/projects", native, expected=201, grant=True)
        call("/api/native/projects", native, expected=503, grant=True)
        results.append("authenticated native grant creates exactly one Git project and refuses overwrite")
        prompt = ("Create calculator.py with add(a,b), and tests/test_calculator.py with one unittest exercising add(2,3)==5. "
                  "Write both real files. Keep the implementation small. Diagnose any test failure and fix calculator.py.")
        command = "python3 -m unittest discover -s tests -v"
        source = Path(project["path"])
        if args.scenario == "repair":
            (source / "calculator.py").write_text("def add(a,b):\n    return a - b\n")
            (source / "tests").mkdir()
            (source / "tests/test_calculator.py").write_text(
                "import unittest\nfrom calculator import add\nclass TestAdd(unittest.TestCase):\n"
                "    def test_add(self): self.assertEqual(add(2,3), 5)\n")
            subprocess.run(["git", "-C", str(source), "add", "--", "calculator.py", "tests/test_calculator.py"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(source), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                            "commit", "-m", "Broken synthetic baseline"], check=True, capture_output=True)
            prompt = "Repair the failing existing calculator.py test. Find the bug, change only calculator.py, and verify the existing tests."
        if args.scenario == "typescript":
            prompt = ("Create offline TypeScript math.ts exporting twice(n:number) and test_math.ts using node:test. "
                      "Add a package.json with type module and npm test running node --test test_math.ts. Use zero dependencies.")
            command = "npm test"
        if args.scenario == "react":
            dependency = ROOT / "desktop/node_modules/react"
            if not dependency.is_dir():
                raise RuntimeError("Existing cached React runtime is unavailable")
            shutil.copytree(dependency, source / "vendor/react")
            (source / ".gitignore").write_text("vendor/\n")
            (source / "package.json").write_text(json.dumps({"type": "module", "scripts": {"test": "node --test test_widget.ts"}}))
            subprocess.run(["git", "-C", str(source), "add", "-f", "--", "vendor/react", ".gitignore", "package.json"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(source), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                            "commit", "-m", "Pin the installed React runtime for the disposable test"],
                           check=True, capture_output=True)
            prompt = ("Create widget.ts and test_widget.ts. An existing package.json runs the test; preserve it. Import the available React runtime from "
                      "./vendor/react/index.js without dependencies. Export a function Widget returning "
                      "React.createElement('button', null, 'Local widget'). Write a node:test test that verifies the result "
                      "type and children, importing the widget with the literal ./widget.ts extension. The test uses native Node TypeScript stripping.")
            command = "npm test"
        if args.scenario in {"pdf", "ocr"}:
            content = "Implement calculator.py with add(a,b). Return a + b. Add tests/test_calculator.py which checks add(2,3) == 5 using unittest."
            if args.scenario == "pdf":
                import pymupdf
                path = output / "requirements.pdf"
                with pymupdf.open() as pdf:
                    page = pdf.new_page()
                    page.insert_textbox(pymupdf.Rect(40, 45, 555, 360), content, fontsize=14)
                    pdf.save(path)
            else:
                from PIL import Image, ImageDraw, ImageFont
                path = output / "requirements.png"
                image = Image.new("RGB", (1150, 220), "white")
                font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 32)
                ImageDraw.Draw(image).multiline_text((40, 36), textwrap.fill(content, 62),
                                                       fill="black", font=font, spacing=15)
                image.save(path)
            info = path.stat()
            attached = call("/api/native/attachments", {"project_id": project["id"], "path": str(path),
                            "device": info.st_dev, "inode": info.st_ino}, expected=201, grant=True)
            assert "calculator.py" in attached["excerpt"]
            results.append(f"selected {args.scenario} attachment extracted locally into the project")
            prompt = "Implement the small Python assignment in the attached source. Use the filenames and function from the attachment. Validate it."
        task = call("/api/tasks", {"project_id": project["id"], "prompt": prompt}, expected=201)
        base = "/api/tasks/" + task["id"] + "/autonomous"
        parameters = {"provider_id": "offline-ollama-" + args.model, "command": command, "rounds": 5, "confirm": True}
        call(base + "/start", {**parameters, "confirm": False}, expected=400)
        call(base + "/start", {**parameters, "command": "python3 -c 'print(1)'"}, expected=400)
        call(base + "/start", parameters, expected=202)
        if args.cancel_resume:
            assert entered.wait(10)
            assert call(base + "/stop", {})["stopping"]
            release.set()
            deadline = time.monotonic() + 10
            while server.project_agent.running(task["id"]) and time.monotonic() < deadline:
                time.sleep(0.1)
            assert call(base)["status"] == "stopped"
            server.STORE.conn.close()
            server.STORE = server.Store()
            call(base + "/start", parameters, expected=202)
            results.append("stops during a model round and resumes after reopening persisted state")
        deadline = time.monotonic() + 550
        while time.monotonic() < deadline:
            run = call(base)
            if run["status"] != "running":
                break
            time.sleep(0.5)
        evidence["run"] = run
        if run["status"] != "complete":
            raise RuntimeError("Agent did not complete: " + run.get("summary", ""))
        paths = {"calculator.py", "tests/test_calculator.py"}
        if args.scenario == "typescript":
            paths = {"math.ts", "test_math.ts", "package.json"}
        elif args.scenario == "react":
            paths = {"widget.ts", "test_widget.ts", "package.json"}
        assert paths.issubset(set(run["files"]))
        root = Path(run["workspace"])
        if args.scenario == "repair":
            assert "return a - b" in (source / "calculator.py").read_text()
        elif args.scenario == "react":
            assert not (source / "widget.ts").exists() and not (source / "test_widget.ts").exists()
        else:
            assert not any((source / path).exists() for path in paths)
        if args.scenario not in {"typescript", "react"}:
            assert (root / "calculator.py").read_text().replace(" ", "").find("returna+b") != -1
        assert run["evidence"][-1]["exit_code"] == 0
        if not args.live and args.scenario == "create":
            assert any(x.get("exit_code") == 1 and "AssertionError" in x["feedback"] for x in run["evidence"])
            results.append("reads an actual failing test and repairs implementation in a later round")
        if not args.live and args.scenario == "typescript":
            assert any("ERR_MODULE_NOT_FOUND" in x.get("feedback", "") for x in run["evidence"])
            results.append("fixes an import in an agent-created test while protecting preexisting validation files")
        results.append("creates or repairs real files, runs contained validation, and preserves initial checkout")
        call(base + "/file?path=..%2Foutside%2Fexternal.txt", expected=400)
        example = {"typescript": "math.ts", "react": "widget.ts"}.get(args.scenario, "calculator.py")
        safe = call(base + "/file?path=" + example)
        assert safe["text"]
        results.append("workspace file endpoint authorizes owned files and rejects traversal")
        review = call(base + "/changes")
        assert set(item["path"] for item in review["files"]).issubset(paths)
        if args.scenario in {"repair", "react"}:
            assert not review["can_apply"]
            call(base + "/apply", {"digest": review["digest"], "confirm": True}, expected=400)
        else:
            assert review["can_apply"]
            call(base + "/apply", {"digest": "wrong", "confirm": True}, expected=400)
            assert call(base + "/apply", {"digest": review["digest"], "confirm": True})["files"] == len(paths)
            for path in paths:
                assert (source / path).read_bytes() == (root / path).read_bytes()
            assert call(base + "/apply", {"digest": review["digest"], "confirm": True})["files"] == len(paths)
        results.append("reviews Git baseline diffs and applies only the exact authorized new files")
        while server.project_agent.running(task["id"]):
            time.sleep(0.05)
        server.STORE.conn.close()
        server.STORE = server.Store()
        assert call(base)["status"] == "complete"
        results.append("run and files remain available after reopening the database")
        evidence["ok"] = True
    except (Exception, AssertionError) as error:
        evidence["ok"] = False
        evidence["error"] = str(error)
    finally:
        server.project_agent.stop_all()
        control.shutdown()
        control.server_close()
        thread.join()
        server.STORE.conn.close()
        evidence["seconds"] = round(time.monotonic() - started, 2)
        (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence, indent=2), flush=True)
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
