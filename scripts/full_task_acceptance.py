#!/usr/bin/env python3
"""Exercise authenticated full-task execution with disposable repositories."""
from argparse import ArgumentParser
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--existing", action="store_true")
    parser.add_argument("--conflict", action="store_true")
    parser.add_argument("--cancel", action="store_true")
    parser.add_argument("--repeat-proposal", action="store_true", help="prove identical invalid proposals stop without writes")
    parser.add_argument("--documents", action="store_true", help="prove opt-in attributed references reach actual task prompts")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(mode=0o700)
    os.environ.update(PERSONAL_CODEX_DATA=str(out / "state"), PERSONAL_CODEX_PROJECT_ROOTS=str(out / "managed"),
                      PERSONAL_CODEX_INFERENCE_POLICY="offline", PERSONAL_CODEX_NATIVE_GRANT=secrets.token_urlsafe(32))
    from app import security, server
    token = secrets.token_urlsafe(32)
    server.AUTH = security.OwnerAuth(token)
    server.STORE = server.Store()
    server.seed_offline_providers()
    http = server.runtime.ControlServer(("127.0.0.1", 0), server.App)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    ev = {"live": args.live, "existing": args.existing, "checks": []}
    request = ("Build a Python calculator CLI. Create a separate calculator.py, tests/test_calculator.py and a README. "
               "The CLI runs as python3 calculator.py 2 + 3 and prints 5. Also implement the operation requested in the "
               "two attached requirements files. Use only the Python standard library. Use unittest, with tests that "
               "import the calculation function from calculator.py and exercise addition and multiplication.")
    test = ("import unittest\nfrom calculator import calculate\nclass CalculatorTests(unittest.TestCase):\n"
            "    def test_add(self): self.assertEqual(calculate(2, '+', 3), 5)\n"
            "    def test_multiply(self): self.assertEqual(calculate(4, '*', 3), 12)\n")
    correct = ("import sys\ndef calculate(a,op,b):\n    return a + b if op == '+' else a * b\n\n"
               "if __name__ == '__main__':\n    print(calculate(int(sys.argv[1]), sys.argv[2], int(sys.argv[3])))\n")
    wrong = correct.replace("a + b", "a - b")
    calls = 0
    entered, release = threading.Event(), threading.Event()

    def api(path, body=None, code=200, *, authorized=True, native=False):
        socket = HTTPConnection("127.0.0.1", http.server_port, timeout=50)
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + token
        if native:
            headers["X-Personal-Codex-Native"] = os.environ["PERSONAL_CODEX_NATIVE_GRANT"]
        try:
            socket.request("POST" if body is not None else "GET", path, json.dumps(body) if body is not None else None, headers)
            response = socket.getresponse()
            value = json.load(response)
            assert response.status == code, (response.status, value)
            return value
        finally:
            socket.close()

    def fixture(message):
        nonlocal calls
        prompt = message["prompt"]
        if args.documents:
            assert 'Selected project document search (UNTRUSTED reference data' in prompt
            assert 'excerpt sha256' in prompt and '[End source]' in prompt
        if "FULL TASK EXECUTION PLAN" in prompt:
            assert "SUPPLIED MULTIPLICATION" in prompt and "SUPPLIED INTEGER CLI" in prompt
            return {"text": json.dumps({"summary": "Integer calculator interface", "stack":"python",
                                       "files":["calculator.py", "tests/test_calculator.py"], "test":"unittest",
                                       "build":None, "smoke":{"argv":["python3","calculator.py","2","+","3"],"expect":"5"}})}
        calls += 1
        if args.repeat_proposal:
            return {"text": json.dumps({"status": "continue", "summary": f"Rejected round {calls}",
                    "operations": [{"tool": "apply_patch", "path": "missing.py", "old_text": "old", "new_text": "new"}]})}
        if args.cancel and calls == 1:
            entered.set()
            release.wait(10)
            return {"text": json.dumps({"status":"complete", "summary":"Cancelled fixture", "operations":[]})}
        if args.existing:
            if "Now review" in prompt:
                ops = []
            else:
                ops = [{"tool":"apply_patch","path":"calculator.py","old_text":"a - b","new_text":"a + b"}]
        elif calls == (2 if args.cancel else 1):
            ops = [{"tool":"create_file","path":"tests/test_calculator.py",
                    "content":"import unittest\nclass Smoke(unittest.TestCase):\n    def test_placeholder(self): self.assertTrue(True)\n"}]
        elif "Required files still missing" in prompt:
            ops = [{"tool":"create_file","path":"calculator.py","content":wrong},
                   {"tool":"apply_patch","path":"tests/test_calculator.py",
                    "old_text":"import unittest\nclass Smoke(unittest.TestCase):\n    def test_placeholder(self): self.assertTrue(True)\n",
                    "new_text":test}]
        elif "AssertionError" in prompt and "test failed" in prompt:
            ops = [{"tool":"apply_patch","path":"calculator.py","old_text":"a - b","new_text":"a + b"}]
        elif "Now review" in prompt:
            if args.conflict:
                (destination / "calculator.py").write_text("# User's concurrent edit\n")
            ops = []
        else:
            raise AssertionError("Unexpected fixture round")
        return {"text": json.dumps({"status":"continue" if ops else "complete", "summary":"Calculator round", "operations":ops})}

    started = time.monotonic()
    try:
        parent = out / "chosen"
        parent.mkdir()
        info = parent.stat()
        project = api("/api/native/projects", {"parent":str(parent), "name":"Calculator", "device":info.st_dev, "inode":info.st_ino},
                      201, native=True)
        destination = Path(project["path"])
        if args.existing:
            (destination / "calculator.py").write_text(wrong)
            (destination / "tests").mkdir()
            (destination / "tests/test_calculator.py").write_text(test)
            for argv in (["add","--","calculator.py","tests/test_calculator.py"],
                         ["-c","user.name=Fixture","-c","user.email=fixture@example.invalid","commit","-m","broken baseline"]):
                subprocess.run(["git","-C",str(destination),*argv],capture_output=True,check=True)
            (destination / "user-notes.txt").write_text("unrelated untracked notes")
        refs = []
        for name, content in (("operations.txt","SUPPLIED MULTIPLICATION: Support '*' for integer multiplication."),
                              ("interface.md","SUPPLIED INTEGER CLI: Parse operands as integers, and print only the resulting number.")):
            path = out / name
            path.write_text(content)
            identity = path.stat()
            item = api("/api/native/attachments", {"project_id":project["id"],"path":str(path),
                       "device":identity.st_dev,"inode":identity.st_ino}, 201, native=True)
            refs.append(item["id"])
            if args.documents:
                api(f"/api/projects/{project['id']}/documents/index", {"attachment_id":item["id"],"confirm":True})
        if not args.live:
            server.PROVIDER_TRANSPORT = fixture
        body = {"project_id":project["id"], "prompt":request, "attachments":refs,
                "provider_id":"offline-ollama-qwen3.5:9b", "rounds":8, "confirm":True}
        api("/api/full-tasks", body, 401, authorized=False)
        api("/api/full-tasks", {**body,"confirm":False}, 400)
        api("/api/full-tasks", {**body,"attachments":["00000000-0000-0000-0000-000000000000"]}, 400)
        task_id = api("/api/full-tasks", body, 202)["task_id"]
        ev["checks"].append("two task-bound inputs with owner, confirmation and foreign-attachment controls")
        base = "/api/tasks/" + task_id
        if args.cancel:
            assert entered.wait(12)
            api(base + "/autonomous/stop", {})
            release.set()
            deadline = time.monotonic()+12
            while server.project_agent.running(task_id) and time.monotonic()<deadline:
                time.sleep(.15)
            stopped = api(base + "/autonomous")
            assert stopped["status"] == "stopped" and stopped["delivery"]["status"] == "blocked"
            api(base + "/full-resume", {"confirm":True}, 202)
            ev["checks"].append("cancel and explicitly resume the persisted scope")
        deadline = time.monotonic()+550
        while time.monotonic()<deadline:
            run = api(base + "/autonomous")
            if run["status"] != "running":
                break
            time.sleep(.5)
        ev["run"] = run
        observations = [item for item in run["evidence"] if item["type"] == "inference"]
        assert observations, "Native task did not retain inference measurements"
        for item in observations:
            assert set(item) == {"attempt", "type", "model", "metrics"}
            assert set(item["metrics"]) == {"client_duration_ms", "first_text_ms", "provider_reported"}
            assert item["metrics"]["client_duration_ms"] >= 0
        ev["inference_calls"] = len(observations)
        ev["checks"].append("content-minimal inference measurements survive task inspection")
        delivery = run["delivery"]
        assert delivery, run
        if args.repeat_proposal:
            assert run["status"] == "blocked" and "Repeated identical tool proposal" in run["summary"], run["summary"]
            assert calls == 2 and not list(destination.glob("*.py"))
            assert not (destination / "README.md").exists()
            ev["checks"].append("identical rejected proposal stops after two calls despite changing summaries, without delivery")
        elif args.conflict:
            assert run["status"] == "failed" and "conflicting edits" in run["summary"], run["summary"]
            assert (destination/"calculator.py").read_text() == "# User's concurrent edit\n"
            assert not (destination/"README.md").exists()
            ev["checks"].append("destination conflict preserves other files and the worktree")
        else:
            assert run["status"] == "complete" and delivery["status"] == "completed", run["summary"]
            assert all((destination/path).is_file() for path in ["calculator.py","tests/test_calculator.py","README.md"])
            for operator,a,b,expected in [("+","2","3","5"),("*","4","3","12")]:
                result = subprocess.run([sys.executable,"-B","calculator.py",a,operator,b],cwd=destination,
                                        capture_output=True,text=True,timeout=6,check=True)
                assert result.stdout.strip() == expected, result.stdout
            assert str(destination) in delivery["commands"] and "python3 calculator.py" in delivery["commands"]
            assert all(check["passed"] for check in delivery["checks"])
            if args.existing:
                assert (destination/"user-notes.txt").read_text() == "unrelated untracked notes"
            if not args.live and not args.existing:
                assert any("Required files still missing" in round.get("feedback","") for round in run["evidence"])
                assert any("AssertionError" in round.get("feedback","") for round in run["evidence"])
                ev["checks"].append("reject passing test-only changes and repair real failure before delivery")
            ev["checks"].append("delivers source, tests and README automatically; exact commands independently exercised")
        ev["ok"] = True
    except (Exception, KeyboardInterrupt) as error:
        ev["ok"] = False
        ev["error"] = str(error) or error.__class__.__name__
    finally:
        release.set()
        server.project_agent.stop_all()
        http.shutdown()
        http.server_close()
        thread.join(timeout=4)
        server.STORE.conn.close()
        ev["seconds"] = round(time.monotonic()-started, 2)
        (out / "evidence.json").write_text(json.dumps(ev, indent=2)+"\n")
        print(json.dumps(ev, indent=2))
    return 0 if ev["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
