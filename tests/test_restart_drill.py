"""A restart must leave no in-flight state behind in any table that has a status column."""
import json
from pathlib import Path
import tempfile
import unittest

from app import server

# Statuses that mean a live worker owns the row. A restart cannot resume such a worker, so none of
# these may survive one. "pending" is deliberately absent: an approval or proposal awaiting a
# decision is a valid resting state.
BLOCKING = ("running", "executing", "streaming", "queued")


def lingering(store):
    tables = [row[0] for row in store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    found = {}
    for table in tables:
        columns = {row[1] for row in store.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "status" not in columns:
            continue
        for row in store.rows(f"SELECT status, COUNT(*) AS n FROM {table} GROUP BY status"):
            if row["status"] in BLOCKING:
                found[table] = found.get(table, 0) + row["n"]
    return found


class RestartDrillTests(unittest.TestCase):
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

    def seed(self):
        store = server.STORE
        stamp = server.now()
        scope = {"identity": [1, 2], "baseline": "a" * 40, "source": str(Path(self.tmp.name).resolve()),
                 "seconds": 120, "attachments": [], "attachment_names": []}
        store.write("INSERT INTO conversations (id,title,model,created_at,updated_at) VALUES (?,?,?,?,?)",
                    ("chat", "Drill", "", stamp, stamp))
        store.write("INSERT INTO messages (id,conversation_id,role,content,status,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)", ("m1", "chat", "user", "keep me", "complete", stamp, stamp))
        store.write("INSERT INTO messages (id,conversation_id,role,content,status,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)", ("m2", "chat", "assistant", "half an ans", "streaming", stamp, stamp))
        store.write("INSERT INTO messages (id,conversation_id,role,content,status,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)", ("m3", "chat", "assistant", "", "queued", stamp, stamp))
        store.write("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)", ("task", "project", "Drill task", "running", "[]", stamp, stamp))
        store.write("INSERT INTO full_tasks VALUES (?,?,NULL,?)",
                    ("task", json.dumps(scope), json.dumps({"status": "partially completed", "files": ["a.py"]})))
        store.write("INSERT INTO rounds (id,task_id,round_number,provider_id,model,prompt_sha256,proposal_id,status,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)", ("round", "task", 1, "provider", "model", "b" * 64, "p1", "executing", stamp, stamp))
        store.write("INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("p1", "task", "branch", "workspace", "summary", "[]", "d" * 64, "executing", None, stamp))
        # Claimed by the proposal-execution route, which has no round to recover it.
        store.write("INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("p2", "task", "branch", "workspace", "summary", "[]", "e" * 64, "executing", None, stamp))
        store.write("INSERT INTO operations (id,task_id,round_id,round_number,op_index,tool,status,started_at) "
                    "VALUES (?,?,?,?,?,?,?,?)", ("op", "task", "round", 1, 0, "apply_patch", "running", stamp))
        store.write("INSERT INTO autonomous_runs VALUES (?,?,?,?,?,?,?,?,?)",
                    ("task", "provider", "full-task", "running", 1, 4, "in flight", "[]", stamp))
        store.write("INSERT INTO inference_jobs (id,provider_id,model,prompt,prompt_sha256,status,deadline,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)", ("j1", "provider", "model", "secret prompt", "digest", "queued", stamp + 60, stamp, stamp))
        store.write("INSERT INTO inference_jobs (id,provider_id,model,prompt,prompt_sha256,status,lease_hash,lease_until,deadline,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("j2", "provider", "model", "secret prompt", "digest", "running",
                                                         "a" * 64, stamp + 15, stamp + 60, stamp, stamp))

    def test_a_restart_closes_every_in_flight_row(self):
        self.seed()
        server.STORE.close()
        server.STORE = server.Store()
        self.assertEqual(lingering(server.STORE), {})

    def test_a_restart_keeps_the_work_it_could_not_finish(self):
        self.seed()
        server.STORE.close()
        server.STORE = server.Store()
        store = server.STORE
        self.assertEqual(store.one("SELECT content,status FROM messages WHERE id='m1'"),
                         {"content": "keep me", "status": "complete"})
        partial = store.one("SELECT content,status,error FROM messages WHERE id='m2'")
        self.assertEqual((partial["content"], partial["status"]), ("half an ans", "stopped"))
        self.assertIn("display-only", partial["error"])
        round_row = store.one("SELECT status,error,proposal_id FROM rounds WHERE id='round'")
        self.assertEqual(round_row["status"], "interrupted")
        self.assertIn("new round", round_row["error"])
        self.assertEqual(store.one("SELECT status FROM proposals WHERE id='p1'")["status"], "interrupted")
        self.assertEqual(store.one("SELECT status FROM proposals WHERE id='p2'")["status"], "interrupted")
        self.assertEqual(store.one("SELECT status FROM operations WHERE id='op'")["status"], "interrupted")
        self.assertEqual(json.loads(store.one("SELECT delivery FROM full_tasks WHERE task_id='task'")["delivery"]),
                         {"status": "partially completed", "files": ["a.py"]})
        self.assertEqual(store.one("SELECT status FROM autonomous_runs WHERE task_id='task'")["status"], "interrupted")
        job = store.one("SELECT status,prompt,content FROM inference_jobs WHERE id='j2'")
        self.assertEqual((job["status"], job["prompt"], job["content"]), ("interrupted", "", ""))
        events = store.rows("SELECT message FROM events WHERE task_id='task'")
        self.assertEqual(len(events), 1)
        self.assertIn("interrupted by a restart", events[0]["message"])


if __name__ == "__main__":
    unittest.main()
