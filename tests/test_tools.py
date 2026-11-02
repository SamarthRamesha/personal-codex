"""Agent tool-call validation, workspace containment, and approval-gated execution."""
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app.server as server
from app.tools import (MAX_OPERATIONS, ToolCallError, apply_patch, bind_hashes, completion_evidence,
                       execute_operations, file_sha256, list_files, parse_proposal, parse_round_proposal,
                       proposal_digest, read_file, resolve_in_workspace, round_feedback, validate_operations)


class ToolValidationTests(unittest.TestCase):
    def test_valid_operations_are_normalised(self):
        operations = validate_operations([
            {"tool": "list_files", "path": "."},
            {"tool": "read_file", "path": "README.md"},
            {"tool": "apply_patch", "path": "README.md", "old_text": "a", "new_text": "b"},
            {"tool": "run_tests", "command": "python3 -m unittest discover -s tests"},
        ])
        self.assertEqual([op["tool"] for op in operations],
                         ["list_files", "read_file", "apply_patch", "run_tests"])
        self.assertEqual((operations[0]["depth"], operations[0]["limit"]), (1, 50))
        self.assertEqual(operations[3]["timeout"], 120)

    def test_unknown_tool_and_arguments_are_rejected(self):
        with self.assertRaises(ToolCallError):
            validate_operations([{"tool": "shell", "command": "rm -rf /"}])
        with self.assertRaises(ToolCallError):
            validate_operations([{"tool": "read_file", "path": "a.txt", "exec": "x"}])
        with self.assertRaises(ToolCallError):
            validate_operations([{"tool": "read_file"}])
        with self.assertRaises(ToolCallError):
            validate_operations([])
        with self.assertRaises(ToolCallError):
            validate_operations([{"tool": "list_files", "path": "."}] * (MAX_OPERATIONS + 1))

    def test_operation_types_are_strict(self):
        with self.assertRaises(ToolCallError):
            validate_operations([{"tool": "read_file", "path": "a.txt", "max_bytes": "10"}])
        with self.assertRaises(ToolCallError):
            validate_operations([{"tool": "list_files", "path": ".", "depth": 9}])
        with self.assertRaises(ToolCallError):
            validate_operations([{"tool": "apply_patch", "path": "a", "old_text": "x", "new_text": "x"}])
        with self.assertRaises(ToolCallError):
            validate_operations([{"tool": "run_tests", "command": "   "}])

    def test_proposal_parsing_rejects_non_json_and_unknown_keys(self):
        with self.assertRaises(ToolCallError):
            parse_proposal("I cannot do that")
        with self.assertRaises(ToolCallError):
            parse_proposal('{"operations": [], "extra": 1}')
        parsed = parse_proposal('```json\n{"summary": "ok", "operations": [{"tool": "list_files", "path": "."}]}\n```')
        self.assertEqual(parsed["summary"], "ok")


class WorkspaceContainmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("print('hi')\n")
        (self.root / "README.md").write_text("readme\n")
        (self.root / ".env").write_text("SECRET=x\n")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text("[core]\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_absolute_traversal_and_secret_paths_are_refused(self):
        for candidate in ("/etc/passwd", "../outside.txt", "src/../../x", ".env", ".git/config", "~/.ssh/id_rsa"):
            with self.assertRaises(ToolCallError):
                resolve_in_workspace(self.root, candidate)

    def test_symlink_escape_is_refused(self):
        link = self.root / "escape"
        link.symlink_to("/etc")
        with self.assertRaises(ToolCallError):
            resolve_in_workspace(self.root, "escape/passwd")

    def test_list_files_excludes_secrets_git_and_respects_limits(self):
        result = list_files(self.root, ".", 3, 10)
        paths = [entry["path"] for entry in result["entries"]]
        self.assertIn("README.md", paths)
        self.assertIn("src/app.py", paths)
        self.assertNotIn(".env", paths)
        self.assertFalse(any(path.startswith(".git") for path in paths))
        self.assertTrue(list_files(self.root, ".", 3, 1)["truncated"])

    def test_read_file_is_bounded_and_hashes_content(self):
        result = read_file(self.root, "src/app.py", 5)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["sha256"], file_sha256(self.root / "src" / "app.py"))

    def test_bind_hashes_requires_existing_target(self):
        operations = validate_operations([{"tool": "apply_patch", "path": "README.md", "old_text": "readme", "new_text": "x"}])
        bound = bind_hashes(self.root, operations)
        self.assertEqual(bound[0]["expected_sha256"], file_sha256(self.root / "README.md"))
        missing = validate_operations([{"tool": "apply_patch", "path": "missing.txt", "old_text": "a", "new_text": "b"}])
        with self.assertRaises(ToolCallError):
            bind_hashes(self.root, missing)

    def test_apply_patch_binds_the_reviewed_hash(self):
        target = self.root / "README.md"
        original = file_sha256(target)
        result = apply_patch(self.root, "README.md", "readme", "changed", original)
        self.assertEqual(target.read_text(), "changed\n")
        self.assertEqual((result["sha256_before"], result["sha256_after"]), (original, file_sha256(target)))
        with self.assertRaises(ToolCallError):
            apply_patch(self.root, "README.md", "changed", "stale", original)

    def test_apply_patch_requires_exactly_one_match(self):
        (self.root / "README.md").write_text("same same\n")
        with self.assertRaises(ToolCallError):
            apply_patch(self.root, "README.md", "same", "once", file_sha256(self.root / "README.md"))

    def test_execution_stops_after_a_failure_and_skips_the_rest(self):
        operations = validate_operations([
            {"tool": "apply_patch", "path": "missing.txt", "old_text": "a", "new_text": "b"},
            {"tool": "read_file", "path": "README.md"},
        ])
        outcome = execute_operations(self.root, operations, runner=None)
        self.assertFalse(outcome["ok"])
        self.assertEqual([entry["status"] for entry in outcome["operations"]], ["error", "skipped"])

    def test_runner_failure_is_recorded(self):
        operations = validate_operations([{"tool": "run_tests", "command": "python3 -c \"raise SystemExit(1)\""}])
        outcome = execute_operations(self.root, operations, runner=lambda command, timeout: {"exit_code": 1, "output": "boom"})
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["operations"][0]["status"], "error")

    def test_digest_binds_task_branch_and_operations(self):
        operations = validate_operations([{"tool": "list_files", "path": "."}])
        self.assertEqual(proposal_digest("t", "b", operations), proposal_digest("t", "b", operations))
        self.assertNotEqual(proposal_digest("t", "b", operations), proposal_digest("t", "other", operations))


@unittest.skipUnless(os.getenv("PERSONAL_CODEX_HTTP_TESTS") == "1", "requires an explicitly enabled loopback listener")
class AgentApiTests(unittest.TestCase):
    """Full proposal → approval → execution lifecycle through the HTTP API."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old = (server.DATA, server.DB_PATH, server.STORE, server.PROVIDER_TRANSPORT)
        server.DATA, server.DB_PATH = base / "control-data", base / "control-data" / "test.db"
        server.STORE = server.Store()
        self.repo = base / "repo"
        self.repo.mkdir()
        for args in (["git", "init"], ["git", "config", "user.email", "t@example.invalid"], ["git", "config", "user.name", "T"]):
            subprocess.run(args, cwd=self.repo, check=True, capture_output=True)
        (self.repo / "README.md").write_text("hi\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.repo, check=True, capture_output=True)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_port}"

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        server.STORE.conn.close()
        server.DATA, server.DB_PATH, server.STORE, server.PROVIDER_TRANSPORT = self.old
        self.tmp.cleanup()

    def call(self, path, method="GET", data=None):
        body = json.dumps(data).encode() if data is not None else None
        request = Request(self.base + path, data=body, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def prepare(self, proposal):
        server.PROVIDER_TRANSPORT = lambda request: {"text": json.dumps(proposal)}
        _, project = self.call("/api/projects", "POST", {"name": "fixture", "path": str(self.repo)})
        _, provider = self.call("/api/providers", "POST", {"kind": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "stub"})
        _, task = self.call("/api/tasks", "POST", {"project_id": project["id"], "prompt": "update the readme"})
        task_id = task["id"]
        _, approval = self.call(f"/api/tasks/{task_id}/workspace-request", "POST", {})
        self.assertEqual(self.call(f"/api/approvals/{approval['id']}", "PATCH", {"status": "approved"})[0], 200)
        status, workspace = self.call(f"/api/tasks/{task_id}/workspace", "POST", {})
        self.assertEqual(status, 201)
        return task_id, provider, workspace

    def test_proposal_requires_approval_then_executes_once(self):
        proposal = {"summary": "update readme", "operations": [
            {"tool": "list_files", "path": "."},
            {"tool": "read_file", "path": "README.md"},
            {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "hello from agent\n"},
            {"tool": "run_tests", "command": 'python3 -c "print(42)"'},
        ]}
        task_id, provider, workspace = self.prepare(proposal)
        status, request_approval = self.call(f"/api/tasks/{task_id}/agent/request", "POST", {"provider_id": provider["id"]})
        self.assertEqual((status, request_approval["kind"]), (201, "provider-invoke"))
        status, denied = self.call(f"/api/tasks/{task_id}/agent/plan", "POST", {"provider_id": provider["id"]})
        self.assertEqual(status, 403)
        self.assertEqual(self.call(f"/api/approvals/{request_approval['approval_id']}", "PATCH", {"status": "approved"})[0], 200)
        status, planned = self.call(f"/api/tasks/{task_id}/agent/plan", "POST", {"provider_id": provider["id"]})
        self.assertEqual(status, 201)
        self.assertEqual(len(planned["operations"]), 4)
        self.assertEqual(len(planned["operations"][2]["expected_sha256"]), 64)
        status, denied = self.call(f"/api/tasks/{task_id}/agent/execute", "POST", {})
        self.assertEqual(status, 403)
        self.assertEqual(self.call(f"/api/approvals/{planned['approval_id']}", "PATCH", {"status": "approved"})[0], 200)
        status, executed = self.call(f"/api/tasks/{task_id}/agent/execute", "POST", {})
        self.assertEqual((status, executed["status"], executed["ok"]), (200, "executed", True))
        self.assertEqual((Path(workspace["path"]) / "README.md").read_text(), "hello from agent\n")
        status, again = self.call(f"/api/tasks/{task_id}/agent/execute", "POST", {})
        self.assertEqual(status, 404)
        status, stored = self.call(f"/api/tasks/{task_id}/agent")
        self.assertEqual((status, stored["status"]), (200, "executed"))
        _, events = self.call(f"/api/tasks/{task_id}/events")
        self.assertTrue(any("Tool apply_patch" in event["message"] for event in events))

    def test_stale_file_state_fails_the_patch_instead_of_overwriting(self):
        proposal = {"summary": "patch", "operations": [
            {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "agent\n"},
        ]}
        task_id, provider, workspace = self.prepare(proposal)
        _, request_approval = self.call(f"/api/tasks/{task_id}/agent/request", "POST", {"provider_id": provider["id"]})
        self.call(f"/api/approvals/{request_approval['approval_id']}", "PATCH", {"status": "approved"})
        _, planned = self.call(f"/api/tasks/{task_id}/agent/plan", "POST", {"provider_id": provider["id"]})
        self.call(f"/api/approvals/{planned['approval_id']}", "PATCH", {"status": "approved"})
        (Path(workspace["path"]) / "README.md").write_text("changed after review\n")
        status, executed = self.call(f"/api/tasks/{task_id}/agent/execute", "POST", {})
        self.assertEqual((status, executed["status"], executed["ok"]), (200, "failed", False))
        self.assertEqual((Path(workspace["path"]) / "README.md").read_text(), "changed after review\n")


if __name__ == "__main__":
    unittest.main()


class RoundProposalUnitTests(unittest.TestCase):
    def test_round_status_and_operations_are_strict(self):
        parsed = parse_round_proposal('{"summary":"fix","status":"continue","operations":[{"tool":"list_files","path":"."}]}')
        self.assertEqual((parsed["status"], len(parsed["operations"])), ("continue", 1))
        with self.assertRaises(ToolCallError):
            parse_round_proposal('{"status":"finish","operations":[]}')
        with self.assertRaises(ToolCallError):
            parse_round_proposal('{"status":"complete","operations":[{"tool":"list_files","path":"."}]}')
        with self.assertRaises(ToolCallError):
            parse_round_proposal('{"status":"continue"}')
        self.assertEqual(parse_round_proposal('{"status":"blocked","summary":"need a key"}')["operations"], [])

    def test_feedback_reports_tests_changes_and_errors(self):
        operations = [{"tool": "apply_patch", "path": "a.py"}, {"tool": "run_tests", "command": "python3 -m unittest"}]
        results = [{"index": 0, "tool": "apply_patch", "status": "ok"},
                   {"index": 1, "tool": "run_tests", "status": "error", "exit_code": 1, "output": "FAIL: test_x\nboom"}]
        feedback = round_feedback(Path("."), operations, results)
        self.assertEqual((feedback["test_exit_code"], feedback["changed_files"]), (1, ["a.py"]))
        self.assertEqual(feedback["failed_tests"], ["FAIL: test_x"])
        self.assertFalse(feedback["ok"])

    def test_completion_needs_executed_work_and_passing_tests(self):
        self.assertFalse(completion_evidence([])[0])
        incomplete = [{"status": "passed", "test_result": {"tests_ran": False, "changed_files": ["a"]}}]
        self.assertFalse(completion_evidence(incomplete)[0])
        no_change = [{"status": "passed", "test_result": {"tests_ran": True, "test_exit_code": 0, "changed_files": []}}]
        self.assertFalse(completion_evidence(no_change)[0])
        stale = [{"status": "passed", "test_result": {"tests_ran": True, "test_exit_code": 0, "changed_files": ["a"]}},
                 {"status": "failed-checks", "test_result": {"tests_ran": True, "test_exit_code": 1, "changed_files": ["b"]}}]
        self.assertFalse(completion_evidence(stale)[0])
        proven = [{"status": "passed", "test_result": {"tests_ran": True, "test_exit_code": 0, "changed_files": ["a"]}}]
        self.assertTrue(completion_evidence(proven)[0])


@unittest.skipUnless(os.getenv("PERSONAL_CODEX_HTTP_TESTS") == "1", "requires an explicitly enabled loopback listener")
class RoundApiFixture(unittest.TestCase):
    """Shared fixture: disposable repo, stub transport, workspace and loopback control plane."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old = (server.DATA, server.DB_PATH, server.STORE, server.PROVIDER_TRANSPORT, server.MAX_ROUNDS)
        server.DATA, server.DB_PATH = base / "control-data", base / "control-data" / "test.db"
        server.STORE = server.Store()
        self.repo = base / "repo"
        self.repo.mkdir()
        for args in (["git", "init"], ["git", "config", "user.email", "t@example.invalid"], ["git", "config", "user.name", "T"]):
            subprocess.run(args, cwd=self.repo, check=True, capture_output=True)
        (self.repo / "README.md").write_text("hi\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.repo, check=True, capture_output=True)
        self.responses = []
        server.PROVIDER_TRANSPORT = lambda request: {"text": self.responses.pop(0)}
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_port}"
        _, project = self.call("/api/projects", "POST", {"name": "fixture", "path": str(self.repo)})
        self.project_id = project["id"]
        _, self.provider = self.call("/api/providers", "POST", {"kind": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "stub"})
        _, task = self.call("/api/tasks", "POST", {"project_id": project["id"], "prompt": "make the readme correct"})
        self.task_id = task["id"]
        _, approval = self.call(f"/api/tasks/{self.task_id}/workspace-request", "POST", {})
        self.call(f"/api/approvals/{approval['id']}", "PATCH", {"status": "approved"})
        _, workspace = self.call(f"/api/tasks/{self.task_id}/workspace", "POST", {})
        self.workspace = Path(workspace["path"])

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join()
        server.STORE.conn.close()
        server.DATA, server.DB_PATH, server.STORE, server.PROVIDER_TRANSPORT, server.MAX_ROUNDS = self.old
        self.tmp.cleanup()

    def call(self, path, method="GET", data=None):
        body = json.dumps(data).encode() if data is not None else None
        request = Request(self.base + path, data=body, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def approve(self, approval_id):
        return self.call(f"/api/approvals/{approval_id}", "PATCH", {"status": "approved"})[0]

    def request_round(self):
        status, payload = self.call(f"/api/tasks/{self.task_id}/agent/round/request", "POST", {"provider_id": self.provider["id"]})
        self.assertEqual(status, 201, payload)
        self.assertEqual(self.approve(payload["approval_id"]), 200)
        return payload

    def plan_round(self, expected=201):
        self.request_round()
        status, payload = self.call(f"/api/tasks/{self.task_id}/agent/round/plan", "POST", {"provider_id": self.provider["id"]})
        self.assertEqual(status, expected, payload)
        return payload

class MultiRoundApiTests(RoundApiFixture):
    """Iterative rounds: execute, feed evidence back, require fresh approvals, verify completion."""

    def test_two_rounds_self_correct_then_verified_completion(self):
        self.responses = [
            json.dumps({"summary": "first attempt", "status": "continue", "operations": [
                {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "attempt one\n"},
                {"tool": "run_tests", "command": 'python3 -c "import sys; sys.exit(1)"'}]}),
            json.dumps({"summary": "fix the check", "status": "continue", "operations": [
                {"tool": "apply_patch", "path": "README.md", "old_text": "attempt one\n", "new_text": "final\n"},
                {"tool": "run_tests", "command": 'python3 -c "print(\'ok\')"'}]}),
            json.dumps({"summary": "task finished", "status": "complete"}),
        ]
        first = self.plan_round()
        self.assertEqual((first["round"], first["status"]), (1, "awaiting-approval"))
        self.approve(first["approval_id"])
        status, executed = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual((status, executed["status"], executed["task_status"]), (200, "failed-checks", "needs-another-round"))
        self.assertEqual((executed["feedback"]["test_exit_code"], executed["feedback"]["changed_files"]), (1, ["README.md"]))

        second = self.plan_round()
        self.assertEqual(second["round"], 2)
        self.approve(second["approval_id"])
        status, executed = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual((status, executed["status"], executed["task_status"]), (200, "passed", "ready-to-complete"))
        self.assertEqual((self.workspace / "README.md").read_text(), "final\n")

        third = self.plan_round()
        self.assertEqual((third["round"], third["status"]), (3, "complete"))
        self.assertIn("round", third["evidence"])
        self.assertEqual(third["report"]["changed_files"], ["README.md"])
        self.assertEqual([test["exit_code"] for test in third["report"]["tests"]], [1, 0])
        self.assertEqual(third["report"]["status"], "completed")

        status, rounds = self.call(f"/api/tasks/{self.task_id}/agent/rounds")
        self.assertEqual(status, 200)
        self.assertEqual([r["status"] for r in rounds["rounds"]], ["failed-checks", "passed", "complete"])
        self.assertEqual(rounds["limits"]["remaining"], 0)

        status, proposals = self.call(f"/api/projects/{self.project_id}/memory/proposals")
        self.assertEqual(status, 200)
        self.assertEqual([p["kind"] for p in proposals["proposals"]], ["summary"])
        self.assertEqual(proposals["proposals"][0]["status"], "pending", "a completion summary is proposed, never stored automatically")
        _, memory = self.call(f"/api/projects/{self.project_id}/memory")
        self.assertEqual(memory["memory"], [])
        _, events = self.call(f"/api/tasks/{self.task_id}/events")
        self.assertTrue(any("Round 2 passed" in e["message"] for e in events))

    def test_each_round_needs_its_own_approval_and_stale_files_fail(self):
        self.responses = [json.dumps({"summary": "patch", "status": "continue", "operations": [
            {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "changed\n"},
            {"tool": "run_tests", "command": 'python3 -c "print(1)"'}]})]
        status, request = self.call(f"/api/tasks/{self.task_id}/agent/round/request", "POST", {"provider_id": self.provider["id"]})
        self.assertEqual(status, 201)
        status, denied = self.call(f"/api/tasks/{self.task_id}/agent/round/plan", "POST", {"provider_id": self.provider["id"]})
        self.assertEqual(status, 403)
        self.approve(request["approval_id"])
        _, planned = self.call(f"/api/tasks/{self.task_id}/agent/round/plan", "POST", {"provider_id": self.provider["id"]})
        status, denied = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual(status, 403)
        (self.workspace / "README.md").write_text("external edit\n")
        self.approve(planned["approval_id"])
        status, executed = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual((status, executed["status"]), (200, "failed"))
        self.assertEqual((self.workspace / "README.md").read_text(), "external edit\n")
        status, again = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual(status, 404)

    def test_false_completion_is_rejected(self):
        self.responses = [json.dumps({"summary": "trust me", "status": "complete"})]
        self.request_round()
        status, refused = self.call(f"/api/tasks/{self.task_id}/agent/round/plan", "POST", {"provider_id": self.provider["id"]})
        self.assertEqual(status, 409)
        self.assertIn("completion rejected", refused["error"])
        self.assertEqual(refused["status"], "rejected-completion")
        status, rounds = self.call(f"/api/tasks/{self.task_id}/agent/rounds")
        self.assertEqual([r["status"] for r in rounds["rounds"]], ["rejected-completion"])
        _, task = self.call(f"/api/tasks")
        self.assertNotEqual(next(t for t in task if t["id"] == self.task_id)["status"], "completed")

    def test_duplicate_provider_response_is_refused(self):
        proposal = json.dumps({"summary": "patch", "status": "continue", "operations": [
            {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "once\n"},
            {"tool": "run_tests", "command": 'python3 -c "print(1)"'}]})
        self.responses = [proposal]
        planned = self.plan_round()
        self.approve(planned["approval_id"])
        status, executed = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual((status, executed["status"]), (200, "passed"))
        self.responses = [proposal]
        self.request_round()
        status, refused = self.call(f"/api/tasks/{self.task_id}/agent/round/plan", "POST", {"provider_id": self.provider["id"]})
        self.assertEqual(status, 409)
        self.assertIn("identical response", refused["error"])

    def test_round_limit_cancellation_and_recovery_state(self):
        server.MAX_ROUNDS = 1
        self.responses = [json.dumps({"summary": "one round only", "status": "continue", "operations": [
            {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "done\n"},
            {"tool": "run_tests", "command": 'python3 -c "print(1)"'}]})]
        planned = self.plan_round()
        status, limited = self.call(f"/api/tasks/{self.task_id}/agent/round/request", "POST", {"provider_id": self.provider["id"]})
        self.assertEqual(status, 409)
        self.assertIn("round limit", limited["error"])
        status, cancelled = self.call(f"/api/tasks/{self.task_id}/agent/round/cancel", "POST", {})
        self.assertEqual((status, cancelled["status"], cancelled["task_status"]), (200, "cancelled", "cancelled"))
        status, after = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual(status, 404)
        status, rounds = self.call(f"/api/tasks/{self.task_id}/agent/rounds")
        self.assertEqual((status, rounds["status"]), (200, "cancelled"))
        self.assertEqual(rounds["rounds"][0]["status"], "cancelled")


class RoundRecoveryTests(unittest.TestCase):
    """A restart mid-execution must leave the loop recoverable, not stuck."""

    def test_interrupted_round_is_released_for_a_new_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, data = Path(tmp) / "test.db", Path(tmp)
            original = (server.DB_PATH, server.DATA)
            server.DB_PATH, server.DATA = db, data
            try:
                store = server.Store()
                store.write("INSERT INTO projects VALUES (?,?,?,?)", ("p1", "demo", tmp, 1))
                store.write("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)", ("t1", "p1", "fix it", "iterating", "[]", 1, 1))
                store.write("INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?)",
                            ("pr1", "t1", "codex/t1", "/tmp/t1", "fix", "[]", "d1", "executing", None, 1))
                store.write("INSERT INTO rounds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            ("r1", "t1", 1, "pv1", "m", "sha", "pr1", "d1", None, "executing",
                             "start", None, None, None, None, 1, 1))
                restarted = server.Store()
                self.assertEqual(restarted.one("SELECT status FROM rounds WHERE id='r1'")["status"], "interrupted")
                self.assertEqual(restarted.one("SELECT status FROM proposals WHERE id='pr1'")["status"], "interrupted")
                self.assertEqual(restarted.one("SELECT status FROM tasks WHERE id='t1'")["status"], "needs-another-round")
                self.assertIn("interrupted", restarted.one("SELECT message FROM events WHERE task_id='t1'")["message"])
            finally:
                server.DB_PATH, server.DATA = original


if __name__ == "__main__":
    unittest.main()


class ReliabilityApiTests(RoundApiFixture):
    """Cancellation, partial-result persistence, crash recovery and cumulative budgets."""

    def test_cancellation_stops_a_running_command_and_preserves_partial_work(self):
        self.responses = [json.dumps({"summary": "long round", "status": "continue", "operations": [
            {"tool": "run_tests", "command": 'python3 -c "print(1)"'},
            {"tool": "run_tests", "command": 'python3 -c "import time; time.sleep(5.0)"'},
            {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "cancelled\n"},
            {"tool": "run_tests", "command": 'python3 -c "print(2)"'}]})]
        planned = self.plan_round()
        self.approve(planned["approval_id"])
        result = {}
        worker = threading.Thread(target=lambda: result.update(
            value=self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})), daemon=True)
        started = time.time()
        worker.start()
        time.sleep(0.7)
        status, cancel = self.call(f"/api/tasks/{self.task_id}/cancel", "POST", {"reason": "test cancellation"})
        self.assertEqual(status, 202, cancel)
        worker.join(timeout=30)
        elapsed = time.time() - started
        status, executed = result["value"]
        self.assertEqual((status, executed["status"], executed["task_status"]), (200, "cancelled", "cancelled"))
        self.assertTrue(executed["cancelled"])
        self.assertEqual([entry["status"] for entry in executed["results"]], ["ok", "cancelled", "cancelled", "cancelled"])
        self.assertEqual(executed["results"][1]["exit_code"], server.CANCEL_EXIT_CODE)
        self.assertLess(elapsed, 4.5, "cancellation must interrupt the running command, not wait for it")
        self.assertEqual((self.workspace / "README.md").read_text(), "hi\n", "a cancelled operation must not be applied")
        self.assertEqual([row["status"] for row in executed["ledger"]], ["ok", "cancelled", "cancelled", "cancelled"])
        status, rounds = self.call(f"/api/tasks/{self.task_id}/agent/rounds")
        self.assertIsNotNone(rounds["cancellation"])
        self.assertEqual(rounds["rounds"][0]["status"], "cancelled")
        approval = server.STORE.one("SELECT * FROM approvals WHERE id=?", (planned["approval_id"],))
        self.assertEqual(approval["status"], "revoked")
        status, _ = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual(status, 404, "a cancelled round must not execute with its old approval")
        status, fresh = self.call(f"/api/tasks/{self.task_id}/agent/round/request", "POST", {"provider_id": self.provider["id"]})
        self.assertEqual(status, 201, fresh)
        self.assertEqual(fresh["round"], 2)

    def test_partial_results_are_persisted_and_interrupted_operations_are_not_replayed(self):
        self.responses = [json.dumps({"summary": "partial", "status": "continue", "operations": [
            {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "one\n"},
            {"tool": "apply_patch", "path": "README.md", "old_text": "missing text", "new_text": "x\n"},
            {"tool": "run_tests", "command": 'python3 -c "print(1)"'}]})]
        planned = self.plan_round()
        self.approve(planned["approval_id"])
        status, executed = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual((status, executed["status"]), (200, "failed"))
        ledger = executed["ledger"]
        self.assertEqual([row["status"] for row in ledger], ["ok", "error", "skipped"])
        self.assertEqual(ledger[0]["applied"], 1)
        self.assertIn("sha256_before", ledger[0]["file_hashes"])
        self.assertEqual((self.workspace / "README.md").read_text(), "one\n")

        server.STORE.write("UPDATE rounds SET status='executing' WHERE id=?", (planned["round_id"],))
        server.STORE.write("UPDATE operations SET status='running' WHERE id=?", (ledger[1]["id"],))
        server.STORE.write("UPDATE proposals SET status='executing' WHERE id=?", (planned["proposal_id"],))
        restarted = server.Store()
        try:
            self.assertEqual(restarted.one("SELECT status FROM operations WHERE id=?", (ledger[1]["id"],))["status"], "interrupted")
            self.assertEqual(restarted.one("SELECT status FROM operations WHERE id=?", (ledger[0]["id"],))["status"], "ok",
                             "completed operations must survive recovery")
            self.assertEqual(restarted.one("SELECT status FROM rounds WHERE id=?", (planned["round_id"],))["status"], "interrupted")
            self.assertEqual((self.workspace / "README.md").read_text(), "one\n", "recovery must never replay a modification")
        finally:
            restarted.conn.close()

    def test_invocation_budget_blocks_new_rounds_and_requires_explicit_reset(self):
        original = server.MAX_INVOCATIONS
        server.MAX_INVOCATIONS = 1
        try:
            self.responses = [json.dumps({"summary": "patch", "status": "continue", "operations": [
                {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "budget\n"}]})]
            planned = self.plan_round()
            self.approve(planned["approval_id"])
            self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
            status, payload = self.call(f"/api/tasks/{self.task_id}/agent/round/request", "POST", {"provider_id": self.provider["id"]})
            self.assertEqual(status, 409, payload)
            self.assertIn("invocation budget", payload["error"])
            self.assertEqual(payload["budget"]["used"]["invocations"], 1)
            _, tasks = self.call("/api/tasks")
            self.assertEqual(next(t for t in tasks if t["id"] == self.task_id)["status"], "budget-exhausted")
            status, _ = self.call(f"/api/tasks/{self.task_id}/agent/budget/reset", "POST", {})
            self.assertEqual(status, 400, "a budget reset must be explicit")
            status, reset = self.call(f"/api/tasks/{self.task_id}/agent/budget/reset", "POST", {"confirm": True})
            self.assertEqual((status, reset["budget"]["used"]["invocations"]), (200, 0))
            self.responses = [json.dumps({"summary": "again", "status": "continue", "operations": [
                {"tool": "read_file", "path": "README.md"}]})]
            status, fresh = self.call(f"/api/tasks/{self.task_id}/agent/round/request", "POST", {"provider_id": self.provider["id"]})
            self.assertEqual(status, 201, fresh)
        finally:
            server.MAX_INVOCATIONS = original

    def test_prompt_budget_refusal_records_why_execution_stopped(self):
        original = server.MAX_PROMPT_BYTES
        server.MAX_PROMPT_BYTES = 1000
        try:
            status, payload = self.call(f"/api/tasks/{self.task_id}/agent/round/request", "POST", {"provider_id": self.provider["id"]})
            self.assertEqual(status, 409, payload)
            self.assertIn("prompt budget", payload["error"])
            _, events = self.call(f"/api/tasks/{self.task_id}/events")
            self.assertTrue(any("refused before any provider call" in event["message"] for event in events))
        finally:
            server.MAX_PROMPT_BYTES = original

    def test_selected_context_is_visible_and_digest_bound_to_the_round(self):
        self.responses = [json.dumps({"summary": "read", "status": "continue", "operations": [
            {"tool": "read_file", "path": "README.md"}]})]
        planned = self.plan_round()
        self.approve(planned["approval_id"])
        self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        status, rounds = self.call(f"/api/tasks/{self.task_id}/agent/rounds")
        self.assertEqual(status, 200)
        entry = rounds["rounds"][0]
        self.assertIsNotNone(entry["context"])
        self.assertEqual(len(entry["context"]["digest"]), 64)
        self.assertTrue(entry["context"]["files"])
        self.assertGreater(rounds["budget"]["used"]["prompt_bytes"], 0)
        status, contexts = self.call(f"/api/tasks/{self.task_id}/agent/context")
        self.assertEqual((status, len(contexts["contexts"])), (200, 1))
        self.assertNotIn("prompt", contexts["contexts"][0])


class BudgetAndMemoryIntegrationTests(RoundApiFixture):
    """Exhaustion of the remaining counters and memory injection into an approved prompt."""

    def test_test_output_budget_stops_further_rounds(self):
        self.responses = [json.dumps({"summary": "noisy", "status": "continue", "operations": [
            {"tool": "run_tests", "command": 'python3 -c "print(\'x\' * 200)"'}]})]
        planned = self.plan_round()
        self.approve(planned["approval_id"])
        original = server.MAX_TEST_OUTPUT_BYTES
        server.MAX_TEST_OUTPUT_BYTES = 10
        try:
            status, executed = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
            self.assertEqual(status, 200, executed)
            self.assertGreater(executed["budget"]["used"]["test_output_bytes"], 10)
            status, refused = self.call(f"/api/tasks/{self.task_id}/agent/round/request", "POST", {"provider_id": self.provider["id"]})
            self.assertEqual((status, "test output budget" in refused["error"]), (409, True), refused)
        finally:
            server.MAX_TEST_OUTPUT_BYTES = original

    def test_project_memory_is_included_in_the_approved_round_prompt(self):
        project_row = server.STORE.one("SELECT project_id FROM tasks WHERE id=?", (self.task_id,))
        status, _ = self.call(f"/api/projects/{project_row['project_id']}/memory", "POST",
                              {"kind": "test-command", "content": "always run python3 -m unittest discover -s tests"})
        self.assertEqual(status, 201)
        payload = self.request_round()
        stored = server.STORE.one("SELECT prompt FROM contexts WHERE task_id=? ORDER BY created_at DESC LIMIT 1", (self.task_id,))
        self.assertIn("always run python3 -m unittest discover", stored["prompt"])
        self.assertIn("possibly stale", stored["prompt"])
        self.assertEqual(payload["budget"]["used"]["context_bytes"] > 0, True)


class MemoryPromotionApiTests(RoundApiFixture):
    """Memory is proposed by a verified round, then explicitly approved or rejected by the user."""

    def passing_round(self):
        self.responses = [json.dumps({"summary": "fix the readme", "status": "continue", "operations": [
            {"tool": "apply_patch", "path": "README.md", "old_text": "hi\n", "new_text": "fixed\n"},
            {"tool": "run_tests", "command": 'python3 -c "print(1)"'}]})]
        planned = self.plan_round()
        self.approve(planned["approval_id"])
        status, executed = self.call(f"/api/tasks/{self.task_id}/agent/round/execute", "POST", {})
        self.assertEqual((status, executed["status"]), (200, "passed"))

    def propose(self, content="Run python3 -m unittest discover -s tests", kind="test-command"):
        return self.call(f"/api/tasks/{self.task_id}/agent/memory/propose", "POST", {"kind": kind, "content": content})

    def test_memory_requires_a_passing_round_and_explicit_approval(self):
        status, refused = self.propose()
        self.assertEqual((status, "passed its checks" in refused["error"]), (409, True), refused)
        self.passing_round()
        status, proposal = self.propose()
        self.assertEqual(status, 201, proposal)
        self.assertEqual(proposal["evidence"]["round"], 1)
        self.assertEqual(proposal["evidence"]["exit_code"], 0)
        self.assertEqual(proposal["evidence"]["changed_files"], ["README.md"])

        status, duplicate = self.propose()
        self.assertEqual(status, 409, duplicate)
        self.assertIn("already exists", duplicate["error"])
        status, bad_kind = self.propose(kind="secret")
        self.assertEqual(status, 400, bad_kind)
        status, credential = self.propose(content="api_key = sk-live-abcdefghijk")
        self.assertEqual(status, 400, credential)

        status, listing = self.call(f"/api/projects/{self.project_id}/memory/proposals")
        self.assertEqual((status, len(listing["proposals"])), (200, 1))
        status, decided = self.call(f"/api/memory-proposals/{proposal['id']}/decide", "POST", {"status": "approved"})
        self.assertEqual(status, 200, decided)
        self.assertEqual((decided.get("status"), decided.get("source_task_id")), ("approved", self.task_id), decided)

        status, memory = self.call(f"/api/projects/{self.project_id}/memory")
        self.assertEqual(status, 200)
        self.assertEqual(len(memory["memory"]), 1)
        entry = memory["memory"][0]
        self.assertEqual((entry["source_task_id"], entry["stale"]), (self.task_id, False))
        self.assertEqual(entry["source"], "round-promotion")

        status, again = self.call(f"/api/memory-proposals/{proposal['id']}/decide", "POST", {"status": "approved"})
        self.assertEqual(status, 409, again)

        self.responses = [json.dumps({"summary": "read", "status": "continue", "operations": [
            {"tool": "read_file", "path": "README.md"}]})]
        self.request_round()
        prompt = server.STORE.one("SELECT prompt FROM contexts WHERE task_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                                  (self.task_id,))["prompt"]
        self.assertIn("Run python3 -m unittest discover -s tests", prompt)
        self.assertIn("verified against a passing round", prompt)

    def test_rejected_proposal_is_never_stored(self):
        self.passing_round()
        _, proposal = self.propose(content="Use the auth module for session checks")
        self.assertEqual(self.call(f"/api/memory-proposals/{proposal['id']}/decide", "POST",
                                   {"status": "rejected", "reason": "not generally true"})[0], 200)
        _, memory = self.call(f"/api/projects/{self.project_id}/memory")
        self.assertEqual(memory["memory"], [])
        status, invalid = self.call(f"/api/memory-proposals/{proposal['id']}/decide", "POST", {"status": "maybe"})
        self.assertEqual(status, 400, invalid)

    def test_stale_memory_is_labelled_and_bounded(self):
        cancelled = server.uid()
        server.STORE.write("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)",
                           (cancelled, self.project_id, "old task", "cancelled", "[]", 1, 1))
        server.STORE.write("INSERT INTO memory (id,project_id,kind,content,source,created_at,updated_at,source_task_id,digest) "
                           "VALUES (?,?,?,?,?,?,?,?,?)",
                           (server.uid(), self.project_id, "issue", "Session refresh used to drop cookies",
                            "round-promotion", 1, 1, cancelled, "digest"))
        _, memory = self.call(f"/api/projects/{self.project_id}/memory")
        self.assertTrue(memory["memory"][0]["stale"])
        lines = server.memory_lines(self.project_id, "fix session refresh cookies", max_bytes=10)
        self.assertEqual(lines, [], "a tiny byte budget must not exceed its cap")
        lines = server.memory_lines(self.project_id, "fix session refresh cookies")
        self.assertEqual(len(lines), 1)
        self.assertIn("possibly stale", lines[0])
