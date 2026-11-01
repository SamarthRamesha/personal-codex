"""Bounded repository context selection: relevance, containment, budget and determinism."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import context


def make_repo(base: Path) -> Path:
    repo = base / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "vendor").mkdir()
    (repo / "README.md").write_text("# Demo\n\nAuth service notes.\n")
    (repo / "ARCHITECTURE.md").write_text("# Architecture\n\nLogin flow lives in src/auth.py.\n")
    (repo / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    (repo / "src" / "auth.py").write_text(
        "class Session:\n    pass\n\n\ndef login(user, password):\n    return user == 'admin' and password == 'x'\n\n\n"
        "def logout(session):\n    return None\n")
    (repo / "src" / "web.js").write_text("export function renderLogin() { return 1 }\nclass Panel { }\n")
    (repo / "tests" / "test_auth.py").write_text("from src.auth import login\n\n\ndef test_login():\n    assert login('a', 'b') is False\n")
    (repo / "vendor" / "ignored.py").write_text("def login():\n    return True\n")
    (repo / ".gitignore").write_text("vendor/\n*.log\n")
    (repo / ".env").write_text("OPENAI_API_KEY=placeholder-value\n")
    (repo / "debug.log").write_text("login debug output\n")
    return repo


class ContextSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_manifest_reports_structure_without_secrets(self):
        manifest = context.manifest(self.repo)
        self.assertGreaterEqual(manifest["file_count"], 6)
        self.assertIn("pyproject.toml", manifest["config_files"])
        self.assertIn("README.md", manifest["documents"])
        for path in manifest["test_files"]:
            self.assertTrue(path.startswith("tests/"))
        self.assertNotIn(".env", context.walk(self.repo))

    def test_gitignore_and_secret_names_are_excluded(self):
        files = context.walk(self.repo)
        self.assertNotIn("vendor/ignored.py", files, "git-ignored directories must be skipped")
        self.assertNotIn("debug.log", files)
        self.assertNotIn(".env", files)
        self.assertIn("src/auth.py", files)

    def test_selection_ranks_task_relevant_files_and_is_deterministic(self):
        first = context.select(self.repo, "fix the login bug in the auth service")
        paths = [snippet["path"] for snippet in first["files"]]
        self.assertIn("src/auth.py", paths)
        self.assertIn("tests/test_auth.py", paths)
        self.assertNotIn(".env", paths)
        second = context.select(self.repo, "fix the login bug in the auth service")
        self.assertEqual(first["digest"], second["digest"], "identical inputs must select identically")
        self.assertEqual([snippet["path"] for snippet in second["files"]], paths)

    def test_selection_respects_byte_and_file_budgets(self):
        small = context.select(self.repo, "fix the login bug", max_bytes=200, max_files=2)
        self.assertLessEqual(small["bytes"], 200)
        self.assertLessEqual(len(small["files"]), 2)
        total = sum(len(snippet["text"].encode("utf-8")) for snippet in small["files"])
        self.assertLessEqual(total, 200)

    def test_changed_files_are_prioritised_and_reasoned(self):
        selection = context.select(self.repo, "adjust the service", changed_files=["src/web.js"])
        paths = [snippet["path"] for snippet in selection["files"]]
        self.assertIn("src/web.js", paths)
        entry = next(snippet for snippet in selection["files"] if snippet["path"] == "src/web.js")
        self.assertIn("changed in an earlier round", entry["reason"])

    def test_symbol_outline_extracts_python_and_javascript(self):
        python = context.outline("src/auth.py", (self.repo / "src" / "auth.py").read_text())
        self.assertEqual([(item["kind"], item["name"]) for item in python],
                         [("class", "Session"), ("function", "login"), ("function", "logout")])
        javascript = context.outline("src/web.js", (self.repo / "src" / "web.js").read_text())
        self.assertIn("renderLogin", [item["name"] for item in javascript])

    def test_symlinks_cannot_escape_the_root(self):
        outside = Path(self.tmp.name) / "outside-secret.txt"
        outside.write_text("SECRET MATERIAL\n")
        link = self.repo / "src" / "linked.py"
        os.symlink(outside, link)
        try:
            self.assertIsNone(context.read_text(self.repo, "src/linked.py"))
            files = context.walk(self.repo)
            self.assertNotIn("src/linked.py", files)
        finally:
            link.unlink()

    def test_prompt_block_marks_repository_text_as_untrusted(self):
        selection = context.select(self.repo, "fix login", memory=["[convention] run pytest -q"])
        block = context.prompt_block(selection, ["[convention] run pytest -q"])
        self.assertIn("untrusted data", block)
        self.assertIn("Project memory", block)
        self.assertIn("src/auth.py", block)
        self.assertNotIn("placeholder-value", block)

    def test_empty_repository_selects_nothing_safely(self):
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        selection = context.select(empty, "do something")
        self.assertEqual(selection["files"], [])
        self.assertTrue(selection["digest"])
        self.assertIn("no relevant files selected", context.prompt_block(selection))


class ContextApiMemoryTests(unittest.TestCase):
    """Memory records are project-scoped, bounded, editable, deletable and free of credentials."""

    def test_memory_crud_rejects_credentials_and_is_scoped(self):
        import json
        import threading
        from http.server import ThreadingHTTPServer
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        import app.server as server

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        repo = base / "repo"; repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        old = (server.DATA, server.DB_PATH, server.STORE)
        server.DATA, server.DB_PATH = base / "data", base / "data" / "test.db"
        server.STORE = server.Store()
        http = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()

        def call(path, method="GET", data=None):
            body = json.dumps(data).encode() if data is not None else None
            request = Request(f"http://127.0.0.1:{http.server_port}{path}", data=body, method=method,
                              headers={"Content-Type": "application/json"})
            try:
                with urlopen(request, timeout=10) as response:
                    return response.status, json.loads(response.read())
            except HTTPError as error:
                return error.code, json.loads(error.read())

        try:
            _, project = call("/api/projects", "POST", {"name": "m", "path": str(repo)})
            status, created = call(f"/api/projects/{project['id']}/memory", "POST",
                                   {"kind": "convention", "content": "Run python3 -m unittest discover -s tests"})
            self.assertEqual(status, 201, created)
            status, denied = call(f"/api/projects/{project['id']}/memory", "POST",
                                  {"kind": "convention", "content": "api_key = sk-live-should-not-be-stored"})
            self.assertEqual(status, 400, denied)
            status, bad_kind = call(f"/api/projects/{project['id']}/memory", "POST", {"kind": "secret", "content": "x"})
            self.assertEqual(status, 400, bad_kind)
            _, listing = call(f"/api/projects/{project['id']}/memory")
            self.assertEqual(len(listing["memory"]), 1)
            status, updated = call(f"/api/projects/{project['id']}/memory/update", "POST",
                                   {"id": created["id"], "content": "Run pytest -q"})
            self.assertEqual((status, updated["status"]), (200, "updated"))
            _, listing = call(f"/api/projects/{project['id']}/memory")
            self.assertEqual(listing["memory"][0]["content"], "Run pytest -q")
            status, deleted = call(f"/api/projects/{project['id']}/memory/delete", "POST", {"id": created["id"]})
            self.assertEqual((status, deleted["status"]), (200, "deleted"))
            _, listing = call(f"/api/projects/{project['id']}/memory")
            self.assertEqual(listing["memory"], [])
        finally:
            http.shutdown(); http.server_close(); thread.join()
            server.STORE.conn.close()
            server.DATA, server.DB_PATH, server.STORE = old


if __name__ == "__main__":
    unittest.main()
