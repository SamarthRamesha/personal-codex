"""A run that cannot even prepare must not keep the single-run slot claimed."""
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from app import project_agent, server


class RunSlotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.old = server.DATA, server.DB_PATH, server.STORE
        server.DATA, server.DB_PATH = root / "data", root / "data/test.db"
        server.STORE = server.Store()
        self.addCleanup(self.restore)
        project = server.uid()
        source = root / "project"
        source.mkdir()
        server.STORE.write("INSERT INTO projects VALUES (?,?,?,?)", (project, "synthetic", str(source), 1))
        self.task = {"id": server.uid(), "project_id": project, "prompt": "Synthetic task",
                     "created_at": 1, "updated_at": 1}
        server.STORE.write("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)",
                           (self.task["id"], project, "Synthetic task", "pending", "[]", 1, 1))
        self.addCleanup(self.release)

    def restore(self):
        server.STORE.close()
        server.DATA, server.DB_PATH, server.STORE = self.old

    def release(self):
        with project_agent._LOCK:
            project_agent._ACTIVE.clear()

    def settle(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        while project_agent.running(self.task["id"]) and time.monotonic() < deadline:
            time.sleep(0.01)
        return project_agent.running(self.task["id"])

    def test_a_run_that_fails_before_its_guard_releases_the_slot(self):
        server.seed_offline_providers()
        identifier = "offline-ollama-qwen3.5:9b"
        task_id = self.task["id"]

        # A saved scope from an older schema: the keys `_run` reads before its try/finally are absent.
        # Only the run's own thread fails, so `start` itself still returns its initial report.
        def fetch(store, identifier):
            if threading.current_thread() is not threading.main_thread():
                raise KeyError("identity")
            return None

        with patch.object(project_agent.full_task, "fetch", side_effect=fetch):
            project_agent.start(server, self.task, {"id": identifier, "model": "synthetic"},
                                "python3 -m unittest", 1)
        self.assertFalse(self.settle(), "the run slot was never released")
        row = server.STORE.one("SELECT status FROM autonomous_runs WHERE task_id=?", (task_id,))
        self.assertEqual(row["status"], "failed")
        self.assertFalse(project_agent.running(task_id))
        with project_agent._LOCK:
            self.assertEqual(project_agent._ACTIVE, {})


if __name__ == "__main__":
    unittest.main()
