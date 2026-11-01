"""Agent tool-call validation, workspace containment, and approval-gated execution."""
import json
import os
import subprocess
import tempfile
import threading
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
class MultiRoundApiTests(unittest.TestCase):
    """Iterative rounds: execute, feed evidence back, require fresh approvals, verify completion."""

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


if __name__ == "__main__":
    unittest.main()
