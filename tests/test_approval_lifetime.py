"""One owner approval authorizes one action, and only while it is fresh."""
from pathlib import Path
import tempfile
import unittest

from app import server


class ApprovalLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.old = server.DATA, server.DB_PATH, server.STORE
        server.DATA, server.DB_PATH = root / "data", root / "data/test.db"
        server.STORE = server.Store()
        self.addCleanup(self.restore)

    def restore(self):
        server.STORE.close()
        server.DATA, server.DB_PATH, server.STORE = self.old

    def pending(self):
        identifier = server.uid()
        server.STORE.write("INSERT INTO approvals (id,project_id,kind,detail,status,created_at) VALUES (?,?,?,?,?,?)",
                           (identifier, "synthetic", "execute", "execute:t:c", "pending", server.now()))
        return identifier

    def row(self, identifier):
        return server.STORE.one("SELECT * FROM approvals WHERE id=?", (identifier,))

    def test_approving_records_a_bounded_lifetime(self):
        identifier = self.pending()
        self.assertTrue(server.STORE.decide_approval(identifier, "approved"))
        row = self.row(identifier)
        self.assertGreater(row["expires_at"], server.now())
        self.assertLessEqual(row["expires_at"], server.now() + server.APPROVAL_SECONDS)

    def test_a_lapsed_approval_cannot_be_spent_and_is_marked_expired(self):
        identifier = self.pending()
        self.assertTrue(server.STORE.decide_approval(identifier, "approved"))
        server.STORE.write("UPDATE approvals SET expires_at=? WHERE id=?", (server.now() - 1, identifier))
        self.assertFalse(server.STORE.consume_approval(identifier))
        self.assertEqual(self.row(identifier)["status"], "expired")
        # It stays unspendable; it never becomes consumable once the clock moves on.
        self.assertFalse(server.STORE.consume_approval(identifier))

    def test_a_fresh_approval_is_still_spent_exactly_once(self):
        identifier = self.pending()
        self.assertTrue(server.STORE.decide_approval(identifier, "approved"))
        self.assertTrue(server.STORE.consume_approval(identifier))
        self.assertEqual(self.row(identifier)["status"], "consumed")
        self.assertFalse(server.STORE.consume_approval(identifier))

    def test_denial_records_no_lifetime(self):
        identifier = self.pending()
        self.assertTrue(server.STORE.decide_approval(identifier, "rejected"))
        row = self.row(identifier)
        self.assertEqual((row["status"], row["expires_at"]), ("rejected", None))

    def test_a_stale_approval_does_not_authorize_a_guarded_setup_route(self):
        identifier = self.pending()
        self.assertTrue(server.STORE.decide_approval(identifier, "approved"))
        server.STORE.write("UPDATE approvals SET expires_at=? WHERE id=?", (server.now() - 1, identifier))
        self.assertIsNone(server.approval_permits("synthetic", "execute", "execute:t:c"))
        self.assertFalse(server.spend_approval("synthetic", "execute", "execute:t:c"))

    def test_a_stale_approval_does_not_shadow_a_fresh_one(self):
        stale = self.pending()
        self.assertTrue(server.STORE.decide_approval(stale, "approved"))
        server.STORE.write("UPDATE approvals SET expires_at=?,created_at=? WHERE id=?",
                           (server.now() - 1, server.now() - 5, stale))
        fresh = self.pending()
        self.assertTrue(server.STORE.decide_approval(fresh, "approved"))
        self.assertEqual(server.approval_permits("synthetic", "execute", "execute:t:c")["id"], fresh)
        self.assertTrue(server.spend_approval("synthetic", "execute", "execute:t:c"))
        self.assertEqual(self.row(fresh)["status"], "consumed")
        self.assertEqual(self.row(stale)["status"], "approved")

    def test_migration_bounds_an_approval_written_before_lifetimes(self):
        identifier = self.pending()
        server.STORE.write("UPDATE approvals SET status='approved', expires_at=NULL WHERE id=?", (identifier,))
        server.STORE.migrate()
        row = self.row(identifier)
        self.assertEqual(row["expires_at"], row["created_at"] + server.APPROVAL_SECONDS)


if __name__ == "__main__":
    unittest.main()
