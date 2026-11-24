"""Read-only project environment readiness.

Every case uses a disposable directory. Nothing here starts a process, contacts a service or
reads a lockfile: the report is built from manifests, local dependency markers and ``stat``.
"""
import json
import os
import shlex
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import app.server as server
from app import environment

SHELL_OPERATORS = {"|", ";", "&&", "||", ">", ">>", "&"}


class EnvironmentReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def ecosystem(self, kind, report=None):
        report = report or environment.inspect(self.root)
        matches = [item for item in report["ecosystems"] if item["kind"] == kind]
        self.assertEqual(len(matches), 1, f"expected exactly one {kind} entry in {report}")
        return matches[0]

    def test_a_node_project_with_a_lockfile_and_dependencies_reports_the_ci_command(self):
        self.write("package.json", json.dumps({"scripts": {"dev": "vite --host 127.0.0.1 --port 1420",
                                                           "build": "tsc -b"}}))
        self.write("package-lock.json", "{}")
        (self.root / "node_modules" / "fixture").mkdir(parents=True)
        report = environment.inspect(self.root)
        node = self.ecosystem("node", report)
        self.assertEqual(node["dependencies"], "installed")
        self.assertEqual(node["lockfile"], "package-lock.json")
        self.assertEqual([step["command"] for step in node["install_steps"]], ["npm ci"])
        self.assertEqual(node["dev_servers"], [{"script": "dev", "declared": "vite --host 127.0.0.1 --port 1420",
                                               "command": "npm run dev", "port": 1420}])
        self.assertFalse(report["executed"])
        self.assertFalse(report["network"])
        self.assertIn("appear installed", report["summary"])

    def test_a_node_project_without_dependencies_or_a_port_says_so(self):
        self.write("package.json", json.dumps({"scripts": {"dev": "vite", "test": "vitest run"}}))
        node = self.ecosystem("node")
        self.assertEqual(node["dependencies"], "missing")
        self.assertEqual([step["command"] for step in node["install_steps"]], ["npm install"])
        self.assertEqual([server["command"] for server in node["dev_servers"]], ["npm run dev"])
        self.assertIsNone(node["dev_servers"][0]["port"])
        self.assertTrue(any("no dev script declares a port" in note for note in node["notes"]))
        self.assertIn("npm install", environment.inspect(self.root)["summary"])

    def test_the_lockfile_chooses_the_package_manager(self):
        self.write("package.json", "{}")
        self.write("pnpm-lock.yaml", "lockfileVersion: 9\n")
        node = self.ecosystem("node")
        self.assertEqual(node["manager"], "pnpm")
        self.assertEqual([step["command"] for step in node["install_steps"]],
                         ["pnpm install --frozen-lockfile"])

    def test_a_python_project_reports_venv_then_pip_as_separate_commands(self):
        self.write("requirements.txt", "respan-gateway==0.3.0\n")
        (self.root / ".venv").mkdir()
        entry = self.ecosystem("python")
        self.assertEqual(entry["dependencies"], "installed")
        self.assertEqual([step["command"] for step in entry["install_steps"]],
                         ["python3 -m venv .venv", ".venv/bin/pip install -r requirements.txt"])

    def test_a_python_project_with_no_environment_is_reported_as_missing(self):
        self.write("requirements.txt", "fixture==1.0\n")
        entry = self.ecosystem("python")
        self.assertEqual(entry["dependencies"], "missing")
        self.assertIn("system interpreter", entry["evidence"])

    def test_a_locked_python_project_uses_its_own_manager(self):
        self.write("pyproject.toml", "[project]\nname='fixture'\n")
        self.write("uv.lock", "version = 1\n")
        entry = self.ecosystem("python")
        self.assertEqual([step["command"] for step in entry["install_steps"]], ["uv sync --frozen"])

    def test_rust_and_go_dependency_state_is_reported_as_unknown_not_guessed(self):
        self.write("Cargo.toml", "[package]\nname='fixture'\n")
        self.write("go.mod", "module fixture\n")
        report = environment.inspect(self.root)
        self.assertEqual([item["kind"] for item in report["ecosystems"]], ["rust", "go"])
        for entry in report["ecosystems"]:
            self.assertEqual(entry["dependencies"], "unknown")
            self.assertTrue(entry["evidence"])
        self.assertIn("unverified", report["summary"])

    def test_an_empty_project_says_no_manifest_was_found(self):
        report = environment.inspect(self.root)
        self.assertEqual(report["ecosystems"], [])
        self.assertIn("No recognised project manifest", report["summary"])
        self.assertFalse(report["executed"])

    def test_an_invalid_manifest_is_reported_instead_of_half_parsed(self):
        self.write("package.json", "{ this is not json")
        node = self.ecosystem("node")
        self.assertEqual(node["manifest_problem"], "invalid JSON")
        self.assertEqual(node["dev_servers"], [])
        self.assertEqual(node["dependencies"], "missing")
        self.assertTrue(any("could not be parsed" in note for note in node["notes"]))

    def test_an_oversized_manifest_is_not_parsed(self):
        self.write("package.json", "x" * (environment.MAX_MANIFEST_BYTES + 1))
        node = self.ecosystem("node")
        self.assertEqual(node["manifest_problem"], "too large")
        self.assertEqual(node["dev_servers"], [])

    def test_a_symlinked_manifest_is_not_followed(self):
        target = self.write("elsewhere.json", json.dumps({"scripts": {"dev": "vite"}}))
        (self.root / "package.json").symlink_to(target)
        report = environment.inspect(self.root)
        self.assertEqual(report["ecosystems"], [])
        self.assertEqual(report["inspected"], [])

    def test_secret_files_are_never_read(self):
        self.write(".env", "OWNER_TOKEN=super-secret-value\n")
        self.write("package.json", "{}")
        rendered = json.dumps(environment.inspect(self.root))
        self.assertNotIn("super-secret-value", rendered)
        self.assertNotIn(".env", rendered)

    def test_every_reported_command_is_one_plain_argv_able_command(self):
        self.write("package.json", json.dumps({"scripts": {"dev": "next dev -p 3000", "start": "node ."}}))
        self.write("requirements.txt", "fixture\n")
        self.write("Cargo.toml", "[package]\nname='fixture'\n")
        self.write("go.mod", "module fixture\n")
        report = environment.inspect(self.root)
        commands = [step["command"] for entry in report["ecosystems"] for step in entry["install_steps"]]
        commands += [item["command"] for entry in report["ecosystems"] for item in entry["dev_servers"]]
        self.assertGreater(len(commands), 4)
        for command in commands:
            self.assertTrue(shlex.split(command), command)
            self.assertFalse(SHELL_OPERATORS & set(shlex.split(command)), command)

    def test_a_missing_project_directory_is_refused(self):
        with self.assertRaises(ValueError):
            environment.inspect(self.root / "does-not-exist")


@unittest.skipUnless(os.getenv("PERSONAL_CODEX_HTTP_TESTS") == "1", "requires an explicitly enabled loopback listener")
class EnvironmentHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old_data, self.old_db, self.old_store = server.DATA, server.DB_PATH, server.STORE
        server.DATA = base / "data"; server.DB_PATH = server.DATA / "test.db"; server.STORE = server.Store()
        self.repo = base / "repo"; self.repo.mkdir()
        (self.repo / "package.json").write_text(json.dumps({"scripts": {"dev": "vite --port 5199"}}))
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_port}"
        self.project = self.request("POST", "/api/projects", {"path": str(self.repo), "name": "Fixture"})

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join()
        server.STORE.close()
        server.DATA, server.DB_PATH, server.STORE = self.old_data, self.old_db, self.old_store
        self.tmp.cleanup()

    def request(self, method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.base + path, data=body, method=method,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read() or b"{}")

    def test_the_readiness_route_reports_the_project_without_acting(self):
        report = self.request("GET", f"/api/projects/{self.project['id']}/environment")
        self.assertFalse(report["executed"])
        self.assertEqual(report["ecosystems"][0]["kind"], "node")
        self.assertEqual(report["ecosystems"][0]["dev_servers"][0]["port"], 5199)
        self.assertEqual(server.STORE.rows("SELECT * FROM executions"), [])
        self.assertFalse((self.repo / "node_modules").exists())

    def test_an_unknown_project_is_a_404(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("GET", "/api/projects/00000000-0000-4000-8000-000000000000/environment")
        self.assertEqual(raised.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
