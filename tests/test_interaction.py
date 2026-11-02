"""Subprocess cancellation, diff review, repository search, and the event stream.

These cover the Milestone 6 gaps that were only partially implemented: cancellation now stops a
running test command, a proposal can be reviewed as a diff with live file digests, the dashboard can
search a repository locally, and activity is streamed from the persisted event log with resumable ids.
"""
import json
import socket
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app.context as context
import app.server as server
import app.tools as tools


class CancellationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old_data = server.DATA
        server.DATA = base / "control-data"
        server.DATA.mkdir(parents=True)
        self.workspace = server.DATA / "ws"
        self.workspace.mkdir()

    def tearDown(self):
        server.DATA = self.old_data
        self.tmp.cleanup()

    def test_running_command_is_stopped_and_partial_output_is_kept(self):
        stop = threading.Event()
        timer = threading.Timer(0.8, stop.set)
        timer.start()
        started = time.time()
        try:
            result = server.execute_in_workspace(
                str(self.workspace), 'python3 -c "import time; print(\'partial-marker\', flush=True); time.sleep(30)"',
                timeout=30, stop_check=stop.is_set)
        finally:
            timer.cancel()
        elapsed = time.time() - started
        self.assertTrue(result["cancelled"])
        self.assertEqual(result["exit_code"], server.CANCEL_EXIT_CODE)
        self.assertLess(elapsed, 12, "cancellation must not wait for the command to finish")
        self.assertIn("partial-marker", result["output"])
        self.assertIn("Cancelled by the operator", result["output"])

    def test_cancellation_leaves_no_child_running(self):
        if not Path("/proc").is_dir():
            self.skipTest("needs /proc to observe the child pid")
        script = ("import os, time; "
                  "open('child.pid','w').write(str(os.getpid())); "
                  "time.sleep(30)")
        stop = threading.Event()
        timer = threading.Timer(0.6, stop.set)
        timer.start()
        try:
            result = server.execute_in_workspace(str(self.workspace), f'python3 -c "{script}"',
                                                 timeout=30, stop_check=stop.is_set)
        finally:
            timer.cancel()
        self.assertEqual(result["exit_code"], server.CANCEL_EXIT_CODE)
        child = int((self.workspace / "child.pid").read_text().strip())
        for _ in range(50):
            if not Path(f"/proc/{child}").exists():
                break
            time.sleep(0.1)
        self.assertFalse(Path(f"/proc/{child}").exists(), "the cancelled command must not keep running")

    def test_completed_command_reports_success_without_cancellation(self):
        result = server.execute_in_workspace(str(self.workspace), 'python3 -c "print(\'done\')"', timeout=10)
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["cancelled"])
        self.assertIn("done", result["output"])

    def test_timeout_is_still_distinct_from_cancellation(self):
        result = server.execute_in_workspace(str(self.workspace), 'python3 -c "import time; time.sleep(5)"', timeout=1)
        self.assertEqual(result["exit_code"], 124)
        self.assertFalse(result["cancelled"])
        self.assertIn("Timed out", result["output"])


class DiffReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "README.md").write_text("alpha\nbeta\ngamma\n")
        (self.root / ".env").write_text("SECRET=x\n")

    def tearDown(self):
        self.tmp.cleanup()

    def operations(self, old="beta", new="beta-changed"):
        return tools.bind_hashes(self.root, tools.validate_operations([
            {"tool": "apply_patch", "path": "README.md", "old_text": old, "new_text": new}]))

    def test_review_reports_hashes_and_a_unified_diff(self):
        operations = self.operations()
        review = tools.review_operations(self.root, operations)
        self.assertFalse(review["stale"])
        entry = review["files"][0]
        self.assertEqual(entry["path"], "README.md")
        self.assertEqual(entry["sha256_current"], tools.file_sha256(self.root / "README.md"))
        self.assertEqual(entry["sha256_current"], entry["expected_sha256"])
        self.assertEqual(entry["occurrences"], 1)
        joined = "\n".join(entry["diff"])
        self.assertIn("-beta", joined)
        self.assertIn("+beta-changed", joined)
        self.assertIn("--- a/README.md", joined)
        self.assertEqual(review["totals"], {"files": 1, "additions": 1, "deletions": 1})
        self.assertFalse(entry["patch_preview_only"])

    def test_review_flags_a_file_changed_after_binding(self):
        operations = self.operations()
        (self.root / "README.md").write_text("rewritten elsewhere\n")
        review = tools.review_operations(self.root, operations)
        self.assertTrue(review["stale"])
        self.assertTrue(review["files"][0]["stale"])
        self.assertNotEqual(review["files"][0]["sha256_current"], review["files"][0]["expected_sha256"])

    def test_review_refuses_escaped_and_secret_paths(self):
        operations = [{"tool": "apply_patch", "path": "../outside.txt", "old_text": "a", "new_text": "b"},
                      {"tool": "apply_patch", "path": ".env", "old_text": "a", "new_text": "b"}]
        review = tools.review_operations(self.root, operations)
        for entry in review["files"]:
            self.assertTrue(entry["stale"])
            self.assertIsNotNone(entry["error"])
        self.assertTrue(review["stale"])

    def test_unmatched_patch_falls_back_to_a_patch_preview(self):
        operations = [{"tool": "apply_patch", "path": "README.md", "old_text": "absent", "new_text": "new"}]
        review = tools.review_operations(self.root, operations)
        entry = review["files"][0]
        self.assertEqual(entry["occurrences"], 0)
        self.assertTrue(entry["patch_preview_only"])
        self.assertIn("+new", "\n".join(entry["diff"]))


class RepositorySearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "app").mkdir()
        (self.root / "app" / "main.py").write_text("def handler():\n    return 'needle here'\n")
        (self.root / "README.md").write_text("no match\n")
        (self.root / ".env").write_text("needle=secret\n")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text("needle\n")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "pkg.js").write_text("needle\n")
        (self.root / ".gitignore").write_text("ignored/\n")
        (self.root / "ignored").mkdir()
        (self.root / "ignored" / "notes.txt").write_text("needle\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_matches_are_located_and_unsafe_locations_are_skipped(self):
        result = context.search(self.root, "NEEDLE")
        paths = {match["path"] for match in result["matches"]}
        self.assertEqual(paths, {"app/main.py"})
        match = result["matches"][0]
        self.assertEqual(match["line"], 2)
        self.assertIn("needle here", match["text"])
        self.assertFalse(result["truncated"])

    def test_query_validation_and_limits(self):
        for query in ("", "   ", "x" * 201):
            with self.assertRaises(ValueError):
                context.search(self.root, query)
        with self.assertRaises(ValueError):
            context.search(self.root, "needle", 0)
        with self.assertRaises(ValueError):
            context.search(self.root, "needle", 51)
        (self.root / "many.txt").write_text("\n".join(["needle"] * 10))
        result = context.search(self.root, "needle", 3)
        self.assertEqual(len(result["matches"]), 3)
        self.assertTrue(result["truncated"])


class InteractionApiTests(unittest.TestCase):
    """Loopback HTTP surface for search, diff review, headers and the event stream."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old = (server.DATA, server.DB_PATH, server.STORE)
        server.DATA, server.DB_PATH = base / "control-data", base / "control-data" / "test.db"
        server.STORE = server.Store()
        self.repo = base / "repo"
        self.repo.mkdir()
        (self.repo / "README.md").write_text("hello interaction\n")
        (self.repo / ".env").write_text("SECRET=x\n")
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_port}"

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)
        server.STORE.conn.close()
        server.DATA, server.DB_PATH, server.STORE = self.old
        self.tmp.cleanup()

    def call(self, path, method="GET", data=None):
        body = json.dumps(data).encode() if data is not None else None
        request = Request(self.base + path, data=body, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def setup_task(self):
        status, project = self.call("/api/projects", "POST", {"name": "repo", "path": str(self.repo)})
        self.assertEqual(status, 201, project)
        status, task = self.call("/api/tasks", "POST", {"project_id": project["id"], "prompt": "find interaction"})
        self.assertEqual(status, 201, task)
        return project, task

    def test_search_endpoint_and_its_validation(self):
        project, _ = self.setup_task()
        status, result = self.call(f"/api/projects/{project['id']}/search?q=hello")
        self.assertEqual(status, 200, result)
        self.assertEqual([m["path"] for m in result["matches"]], ["README.md"])
        self.assertNotIn("SECRET", json.dumps(result))
        status, error = self.call(f"/api/projects/{project['id']}/search?q=")
        self.assertEqual(status, 400)
        self.assertIn("non-empty", error["error"])
        status, missing = self.call("/api/projects/nope/search?q=x")
        self.assertEqual(status, 404)

    def test_diff_endpoint_reports_no_pending_proposal_clearly(self):
        _, task = self.setup_task()
        status, body = self.call(f"/api/tasks/{task['id']}/agent/diff")
        self.assertEqual(status, 404)
        self.assertIn("no pending proposal", body["error"])

    def test_security_headers_are_sent_for_pages_and_api(self):
        with urlopen(self.base + "/", timeout=10) as page:
            self.assertEqual(page.status, 200)
            self.assertEqual(page.headers["X-Content-Type-Options"], "nosniff")
            policy = page.headers["Content-Security-Policy"]
            self.assertIn("default-src 'self'", policy)
            self.assertNotIn("unsafe-inline", policy)
            self.assertEqual(page.headers["X-Frame-Options"], "DENY")
        with urlopen(self.base + "/api/health", timeout=10) as health:
            self.assertEqual(health.headers["Cache-Control"], "no-store")
            self.assertIn("default-src 'none'", health.headers["Content-Security-Policy"])

    def test_event_stream_replays_persisted_events_and_resumes_by_id(self):
        _, task = self.setup_task()
        server.task_event(task["id"], "orchestrator", "info", "first-streamed-event")
        server.task_event(task["id"], "executor", "info", "second-streamed-event")
        first = server.STORE.one("SELECT rowid AS seq FROM events WHERE task_id=? AND message='first-streamed-event'", (task["id"],))
        with socket.create_connection(("127.0.0.1", self.http.server_port), timeout=10) as sock:
            sock.sendall((f"GET /api/tasks/{task['id']}/events/stream HTTP/1.1\r\nHost: localhost\r\n"
                          f"Last-Event-ID: {first['seq']}\r\n\r\n").encode())
            data = b""
            deadline = time.time() + 8
            while b"second-streamed-event" not in data and time.time() < deadline:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        text = data.decode("utf-8", errors="replace")
        self.assertIn("text/event-stream", text)
        self.assertIn("second-streamed-event", text)
        self.assertNotIn("first-streamed-event", text, "Last-Event-ID must resume rather than replay history")

    def test_event_stream_rejects_unknown_tasks(self):
        status, body = self.call("/api/tasks/missing/events/stream")
        self.assertEqual(status, 404)
        self.assertIn("not found", body["error"])


if __name__ == "__main__":
    unittest.main()
