"""Memory admission, provenance and atomic decisions against disposable state."""
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from app import security, server


class MemoryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old = server.DATA, server.DB_PATH, server.STORE, server.AUTH
        root = Path(self.tmp.name)
        server.DATA, server.DB_PATH = root / "state", root / "state" / "test.db"
        server.STORE = server.Store()
        self.addCleanup(self.restore)
        server.AUTH = security.OwnerAuth("synthetic-memory-owner-token-000000000")
        self.project = server.uid()
        self.task = server.uid()
        server.STORE.write("INSERT INTO projects VALUES (?,?,?,?)", (self.project, "synthetic", str(root), 1))
        server.STORE.write("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)",
                           (self.task, self.project, "synthetic task", "completed", "[]", 1, 1))

    def restore(self):
        server.STORE.close()
        server.DATA, server.DB_PATH, server.STORE, server.AUTH = self.old

    def proposal(self, content="Run the local regression suite"):
        proof = {"task_id": self.task, "round": 1, "tests": "python3 -m unittest", "exit_code": 0,
                 "changed_files": ["example.py"], "note": "synthetic evidence"}
        digest = hashlib.sha256(json.dumps({"kind": "convention", "content": content,
                                           "evidence": proof}, sort_keys=True).encode()).hexdigest()
        proposal = server.uid()
        server.STORE.write("INSERT INTO memory_proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (proposal, self.project, self.task, server.uid(), "convention", content,
                            json.dumps(proof), digest, "pending", None, 1, None))
        return proposal

    def manual(self, content="Run the local regression suite"):
        identifier = server.uid()
        server.STORE.write("INSERT INTO memory (id,project_id,kind,content,source,created_at,updated_at) "
                           "VALUES (?,?,?,?,?,?,?)", (identifier, self.project, "convention", content, "manual", 1, 1))
        return identifier

    def call(self, suffix, payload):
        http = server.runtime.ControlServer(("127.0.0.1", 0), server.App)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection("127.0.0.1", http.server_port, timeout=5)
        try:
            connection.request("POST", f"/api/projects/{self.project}/memory{suffix}", json.dumps(payload),
                               {"Content-Type": "application/json", "Authorization": "Bearer synthetic-memory-owner-token-000000000"})
            response = connection.getresponse()
            return response.status, json.load(response)
        finally:
            connection.close()
            http.shutdown()
            http.server_close()
            thread.join(timeout=3)

    def test_edit_cannot_bypass_credential_screening(self):
        identifier = self.manual()
        before = server.STORE.one("SELECT * FROM memory WHERE id=?", (identifier,))
        status, result = self.call("/update", {"id": identifier, "content": "api_key = synthetic-private-value"})
        self.assertEqual(status, 400, result)
        self.assertEqual(server.STORE.one("SELECT * FROM memory WHERE id=?", (identifier,)), before)

    def test_manual_memory_does_not_claim_passing_round_verification(self):
        self.manual()
        prompt = "\n".join(server.memory_lines(self.project))
        self.assertIn("user-provided", prompt)
        self.assertNotIn("verified against a passing round", prompt)

    def test_edit_clears_old_proof_without_destroying_the_proposal_audit(self):
        proposal = self.proposal()
        identifier = server.decide_memory(proposal, True)["id"]
        original = server.STORE.one("SELECT * FROM memory_proposals WHERE id=?", (proposal,))
        status, result = self.call("/update", {"id": identifier, "content": "A newly supplied convention"})
        self.assertEqual(status, 200, result)
        row = server.STORE.one("SELECT * FROM memory WHERE id=?", (identifier,))
        for field in ("source_task_id", "source_round_id", "evidence", "digest"):
            self.assertIsNone(row[field], field)
        self.assertEqual(row["source"], "manual-edit")
        self.assertEqual(server.STORE.one("SELECT * FROM memory_proposals WHERE id=?", (proposal,)), original)

    def test_promotion_respects_project_capacity_and_keeps_pending_decision(self):
        for index in range(200):
            self.manual(f"Distinct convention {index}")
        proposal = self.proposal()
        with self.assertRaisesRegex(ValueError, "limit"):
            server.decide_memory(proposal, True)
        self.assertEqual(server.STORE.one("SELECT COUNT(*) AS n FROM memory")["n"], 200)
        self.assertEqual(server.STORE.one("SELECT status FROM memory_proposals WHERE id=?", (proposal,))["status"], "pending")

    def test_failed_decision_write_rolls_back_the_memory_insert(self):
        proposal = self.proposal()
        server.STORE.write("CREATE TRIGGER reject_decision BEFORE UPDATE ON memory_proposals "
                           "BEGIN SELECT RAISE(ABORT, 'synthetic decision failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            server.decide_memory(proposal, True)
        self.assertEqual(server.STORE.one("SELECT COUNT(*) AS n FROM memory")["n"], 0)
        self.assertEqual(server.STORE.one("SELECT status FROM memory_proposals WHERE id=?", (proposal,))["status"], "pending")

    def test_internal_proposals_use_the_same_credential_policy(self):
        passing = [{"status": "passed", "id": server.uid(), "round_number": 1, "test_result": {}}]
        with patch.object(server, "decoded_rounds", return_value=passing):
            with self.assertRaisesRegex(ValueError, "credential"):
                server.propose_memory({"id": self.task, "project_id": self.project}, "convention", "token=synthetic-value")
        self.assertEqual(server.STORE.one("SELECT COUNT(*) AS n FROM memory_proposals")["n"], 0)

    def test_saved_unsafe_proposal_is_rechecked_before_promotion(self):
        proposal = self.proposal("password=synthetic-value")
        with self.assertRaisesRegex(ValueError, "credential"):
            server.decide_memory(proposal, True)
        self.assertEqual(server.STORE.one("SELECT COUNT(*) AS n FROM memory")["n"], 0)

    def test_changed_content_cannot_reuse_a_provenance_digest(self):
        identifier = server.decide_memory(self.proposal(), True)["id"]
        self.assertIn("verified against a passing round", "\n".join(server.memory_lines(self.project)))
        server.STORE.write("UPDATE memory SET content='Unrelated altered claim' WHERE id=?", (identifier,))
        self.assertTrue(server.memory_rows(self.project)[0]["stale"])
        self.assertNotIn("verified against a passing round", "\n".join(server.memory_lines(self.project)))

    def test_cross_project_task_cannot_supply_verification(self):
        server.decide_memory(self.proposal(), True)
        server.STORE.write("UPDATE tasks SET project_id=? WHERE id=?", (server.uid(), self.task))
        self.assertTrue(server.memory_rows(self.project)[0]["stale"])

    def test_legacy_credential_record_is_not_injected_or_silently_deleted(self):
        identifier = self.manual("token=synthetic-value")
        self.assertEqual(server.memory_lines(self.project), [])
        self.assertIsNotNone(server.STORE.one("SELECT id FROM memory WHERE id=?", (identifier,)))

    def test_changed_proposal_is_not_promoted_with_old_review_digest(self):
        proposal = self.proposal()
        server.STORE.write("UPDATE memory_proposals SET content='Changed after review' WHERE id=?", (proposal,))
        with self.assertRaisesRegex(ValueError, "changed after review"):
            server.decide_memory(proposal, True)
        self.assertEqual(server.STORE.one("SELECT COUNT(*) AS n FROM memory")["n"], 0)

    def race(self, actions):
        barrier = threading.Barrier(len(actions))
        outcomes, unexpected = [], []
        def run(action):
            barrier.wait(timeout=5)
            try:
                action()
                outcomes.append("saved")
            except ValueError:
                outcomes.append("refused")
            except Exception as error:
                unexpected.append(error)
        workers = [threading.Thread(target=run, args=(action,)) for action in actions]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
        self.assertEqual(unexpected, [])
        self.assertCountEqual(outcomes, ["saved", "refused"])

    def test_competing_decisions_cannot_promote_twice(self):
        proposal = self.proposal()
        self.race([lambda: server.decide_memory(proposal, True)] * 2)
        self.assertEqual(server.STORE.one("SELECT COUNT(*) AS n FROM memory")["n"], 1)

    def test_manual_and_promoted_memory_share_the_last_capacity_slot(self):
        for index in range(199):
            self.manual(f"Distinct convention {index}")
        proposal = self.proposal()
        self.race([lambda: server.decide_memory(proposal, True),
                   lambda: server.record_manual_memory(self.project, "convention", "New manual convention", "manual")])
        self.assertEqual(server.STORE.one("SELECT COUNT(*) AS n FROM memory")["n"], 200)

    def test_project_limit_does_not_prevent_other_project_memory(self):
        for index in range(200):
            self.manual(f"Distinct convention {index}")
        other_project = server.uid()
        identifier = server.record_manual_memory(other_project, "convention", "Other project", "manual")
        self.assertEqual(server.memory_rows(other_project)[0]["id"], identifier)


if __name__ == "__main__":
    unittest.main()
