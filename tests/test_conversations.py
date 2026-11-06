"""Conversation persistence and genuine streamed assistant output.

Every provider call here is a deterministic injectable transport; no model and no socket are used.
The HTTP tests exercise the real control plane, including SSE token delivery and resumption.
"""
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import app.server as server
from app import conversations, providers


def streaming_transport(pieces=("Hello", " world"), delay=0.0):
    """Fake adapter that leaks deltas through on_text exactly like a real streaming adapter."""
    def transport(request):
        request["on_text"]("")  # empty deltas must be ignored, not stored
        for piece in pieces:
            if delay:
                time.sleep(delay)
            if request["stop_check"]():
                raise providers.ProviderTransportError("provider stream cancelled before completion")
            request["on_text"](piece)
        return {"text": "".join(pieces), "model": request.get("model"), "streamed": True}
    return transport


def slow_transport():
    """Adapter that keeps streaming until stopped, so a stop request has a window to land."""
    def transport(request):
        for _ in range(200):
            if request["stop_check"]():
                raise providers.ProviderTransportError("provider stream cancelled before completion")
            request["on_text"]("chunk ")
            time.sleep(0.02)
        return {"text": "never", "streamed": True}
    return transport


def failing_transport(message="Provider connection failed: ConnectionRefusedError"):
    def transport(request):
        raise providers.ProviderTransportError(message)
    return transport


class ConversationStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data, self.old_db, self.old_store = server.DATA, server.DB_PATH, server.STORE
        server.DATA = Path(self.tmp.name) / "data"
        server.DB_PATH = server.DATA / "test.db"
        server.STORE = server.Store()
        self.store = server.STORE
        self.old_transport = conversations.TRANSPORT
        conversations.TRANSPORT = streaming_transport()
        self.project = self.store.one("SELECT * FROM projects LIMIT 1")
        if not self.project:
            pid = "project-fixture"
            self.store.write("INSERT INTO projects VALUES (?,?,?,?)", (pid, "Fixture", self.tmp.name, server.now()))
            self.project = self.store.one("SELECT * FROM projects WHERE id=?", (pid,))
        pid = "provider-fixture"
        self.store.write("INSERT INTO providers (id,kind,endpoint,model,secret_ref,cloud_allowed,enabled,created_at) "
                         "VALUES (?,?,?,?,?,?,?,?)", (pid, "ollama", "http://127.0.0.1:11434", "fixture:1b", "", 0, 1, server.now()))
        self.provider_id = pid

    def tearDown(self):
        conversations.TRANSPORT = self.old_transport
        server.STORE.conn.close()
        server.DATA, server.DB_PATH, server.STORE = self.old_data, self.old_db, self.old_store
        self.tmp.cleanup()

    def conversation(self, **extra):
        return conversations.create_conversation(self.store, project_id=self.project["id"], provider_id=self.provider_id, **extra)

    def test_conversation_lifecycle_and_listing(self):
        row = self.conversation()
        self.assertEqual(row["title"], "New conversation")
        self.assertFalse(row["pinned"])
        renamed = conversations.update_conversation(self.store, row["id"], {"title": "  Fix   the  parser ", "pinned": True})
        self.assertEqual(renamed["title"], "Fix the parser")
        self.assertTrue(renamed["pinned"])
        listed = conversations.list_conversations(self.store)
        self.assertEqual(listed[0]["id"], row["id"])
        self.assertTrue(listed[0]["pinned"])
        conversations.update_conversation(self.store, row["id"], {"archived": True})
        self.assertEqual(conversations.list_conversations(self.store), [])
        self.assertEqual(len(conversations.list_conversations(self.store, archived=True)), 1)
        deleted = conversations.delete_conversation(self.store, row["id"])
        self.assertEqual(deleted["status"], "deleted")
        self.assertTrue(deleted["recoverable"])
        self.assertIsNone(conversations.conversation_detail(self.store, row["id"]))
        self.assertEqual(conversations.list_conversations(self.store, archived=True), [])

    def test_invalid_conversation_updates_are_rejected(self):
        row = self.conversation()
        with self.assertRaises(ValueError):
            conversations.update_conversation(self.store, row["id"], {"title": "   "})
        with self.assertRaises(ValueError):
            conversations.update_conversation(self.store, row["id"], {"pinned": "yes"})
        with self.assertRaises(LookupError):
            conversations.create_conversation(self.store, provider_id="missing")
        with self.assertRaises(LookupError):
            conversations.update_conversation(self.store, row["id"], {"project_id": "missing"})

    def test_message_persists_across_a_restart(self):
        row = self.conversation()
        conversations.new_message(self.store, row["id"], "user", "remember this line")
        self.store.conn.close()
        server.STORE = server.Store()
        self.store = server.STORE
        detail = conversations.conversation_detail(self.store, row["id"])
        self.assertEqual(detail["messages"][0]["content"], "remember this line")

    def test_prompt_is_bounded_and_excludes_incomplete_turns(self):
        row = self.conversation()
        conversations.new_message(self.store, row["id"], "user", "u" * 15_000)
        conversations.new_message(self.store, row["id"], "assistant", "a" * 15_000)
        conversations.new_message(self.store, row["id"], "assistant", "partial", status="streaming")
        prompt = conversations.build_prompt(conversations.message_history(self.store, row["id"]))
        self.assertLessEqual(len(prompt), conversations.MAX_PROMPT_CHARS + conversations.MAX_CHUNK_CHARS * 2 + 400)
        self.assertNotIn("partial", prompt)
        self.assertTrue(prompt.rstrip().endswith("ASSISTANT:"))

    def test_oversized_and_empty_messages_are_rejected(self):
        row = self.conversation()
        with self.assertRaises(ValueError):
            conversations.new_message(self.store, row["id"], "user", "x" * (conversations.MAX_MESSAGE_CHARS + 1))
        with self.assertRaises(ValueError):
            conversations.start_turn(self.store, row, "   ", provider=self.store.one("SELECT * FROM providers WHERE id=?", (self.provider_id,)))
        with self.assertRaises(ValueError):
            conversations.new_message(self.store, row["id"], "tool", "x")

    def test_a_turn_streams_tokens_and_completes_with_authoritative_text(self):
        row = self.conversation()
        result = conversations.start_turn(self.store, row, "What is the parser bug?")
        final = conversations.wait_for_message(self.store, result["assistant_message_id"])
        self.assertEqual(final["status"], "complete")
        self.assertEqual(final["content"], "Hello world")
        self.assertGreaterEqual(final["latency_ms"], 0)
        chunks = self.store.rows("SELECT seq,text FROM message_chunks WHERE message_id=? ORDER BY seq", (final["id"],))
        self.assertEqual([chunk["text"] for chunk in chunks], ["Hello", " world"])
        detail = conversations.conversation_detail(self.store, row["id"])
        self.assertEqual([m["role"] for m in detail["messages"]], ["user", "assistant"])
        self.assertEqual(detail["title"], "What is the parser bug?")

    def test_stream_resumes_after_a_sequence_number_without_duplicates(self):
        row = self.conversation()
        result = conversations.start_turn(self.store, row, "stream please")
        mid = result["assistant_message_id"]
        conversations.wait_for_message(self.store, mid)
        events = list(conversations.stream_events(self.store, row["id"], mid))
        tokens = [payload for event, payload in events if event == "token"]
        self.assertEqual([token["text"] for token in tokens], ["Hello", " world"])
        resumed = list(conversations.stream_events(self.store, row["id"], mid, tokens[0]["seq"]))
        self.assertEqual([payload["text"] for event, payload in resumed if event == "token"], [" world"])
        self.assertEqual([event for event, _ in resumed][-1], "done")

    def test_stop_records_a_partial_answer_as_stopped(self):
        conversations.TRANSPORT = slow_transport()
        row = self.conversation()
        result = conversations.start_turn(self.store, row, "long answer")
        mid = result["assistant_message_id"]
        deadline = time.time() + 5
        while time.time() < deadline and not self.store.one("SELECT 1 FROM message_chunks WHERE message_id=? LIMIT 1", (mid,)):
            time.sleep(0.02)
        conversations.request_stop(mid)
        final = conversations.wait_for_message(self.store, mid)
        self.assertEqual(final["status"], "stopped")
        self.assertIn("Stopped by operator", final["error"])
        self.assertTrue(final["content"].startswith("chunk"))
        self.assertNotEqual(final["content"], "never")

    def test_provider_failure_is_recorded_without_taking_the_server_down(self):
        conversations.TRANSPORT = failing_transport()
        row = self.conversation()
        result = conversations.start_turn(self.store, row, "hello")
        final = conversations.wait_for_message(self.store, result["assistant_message_id"])
        self.assertEqual(final["status"], "error")
        self.assertIn("ConnectionRefusedError", final["error"])

    def test_deleting_a_conversation_stops_a_running_answer(self):
        conversations.TRANSPORT = slow_transport()
        row = self.conversation()
        result = conversations.start_turn(self.store, row, "stop me")
        deleted = conversations.delete_conversation(self.store, row["id"])
        self.assertEqual(deleted["stopped_messages"], 1)
        final = conversations.wait_for_message(self.store, result["assistant_message_id"])
        self.assertEqual(final["status"], "stopped")

    def test_search_matches_messages_only_in_live_conversations(self):
        row = self.conversation()
        conversations.new_message(self.store, row["id"], "user", "traceback in parser.py line 40")
        hits = conversations.search_messages(self.store, "traceback")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["conversation_id"], row["id"])
        with self.assertRaises(ValueError):
            conversations.search_messages(self.store, "   ")
        conversations.delete_conversation(self.store, row["id"])
        self.assertEqual(conversations.search_messages(self.store, "traceback"), [])
        # LIKE wildcards are escaped, so a literal % is not a match-everything query.
        self.assertEqual(conversations.search_messages(self.store, "%"), [])

    def test_regenerate_reuses_the_last_user_turn(self):
        row = self.conversation()
        first = conversations.start_turn(self.store, row, "explain the bug")
        conversations.wait_for_message(self.store, first["assistant_message_id"])
        provider = self.store.one("SELECT * FROM providers WHERE id=?", (self.provider_id,))
        second = conversations.start_turn(self.store, row, "", provider=provider, regenerate=True)
        conversations.wait_for_message(self.store, second["assistant_message_id"])
        self.assertTrue(second["regenerated"])
        self.assertIsNone(second["user_message"])
        detail = conversations.conversation_detail(self.store, row["id"])
        self.assertEqual([m["role"] for m in detail["messages"]], ["user", "assistant", "assistant"])

    def test_restart_closes_interrupted_answers_as_terminal(self):
        row = self.conversation()
        streamed = conversations.new_message(self.store, row["id"], "assistant", "half an answer", status="streaming")
        queued = conversations.new_message(self.store, row["id"], "assistant", "", status="queued")
        self.assertTrue(conversations.conversation_report(self.store, row["id"])["streaming"])
        # A restart drops every worker thread; sqlite is the only state that survives.
        self.store.conn.close()
        server.STORE = server.Store()
        self.store = server.STORE
        for message_id in (streamed["id"], queued["id"]):
            recovered = self.store.one("SELECT * FROM messages WHERE id=?", (message_id,))
            self.assertEqual(recovered["status"], "stopped")
            self.assertIn("restarted before this answer finished", recovered["error"])
        report = conversations.conversation_report(self.store, row["id"])
        self.assertFalse(report["streaming"])
        self.assertEqual(report["active_messages"], [])
        # Partial text is display-only and must not reach the next model prompt.
        prompt = conversations.build_prompt(conversations.message_history(self.store, row["id"]))
        self.assertNotIn("half an answer", prompt)
        # An SSE client receives a terminal event instead of waiting for a worker that is gone.
        events = list(conversations.stream_events(self.store, row["id"], streamed["id"]))
        self.assertEqual(events[-1][0], "done")
        self.assertEqual(events[-1][1]["status"], "stopped")
        self.assertIn("restarted", events[-1][1]["error"])

    def test_a_missing_provider_is_refused_rather_than_guessed(self):
        row = conversations.create_conversation(self.store)
        with self.assertRaises(ValueError):
            conversations.resolve_provider(self.store, row, None)
        self.store.write("UPDATE providers SET enabled=0 WHERE id=?", (self.provider_id,))
        with self.assertRaises(ValueError):
            conversations.resolve_provider(self.store, row, self.provider_id)


@unittest.skipUnless(os.getenv("PERSONAL_CODEX_HTTP_TESTS") == "1", "requires an explicitly enabled loopback listener")
class ConversationHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old_data, self.old_db, self.old_store = server.DATA, server.DB_PATH, server.STORE
        server.DATA = base / "data"; server.DB_PATH = server.DATA / "test.db"; server.STORE = server.Store()
        self.old_transport = conversations.TRANSPORT
        conversations.TRANSPORT = streaming_transport()
        self.repo = base / "repo"; self.repo.mkdir()
        (self.repo / "README.md").write_text("# fixture\n")
        import subprocess
        for args in (["git", "init"], ["git", "config", "user.email", "t@example.invalid"],
                     ["git", "config", "user.name", "T"], ["git", "add", "README.md"], ["git", "commit", "-m", "fixture"]):
            subprocess.run(args, cwd=self.repo, check=True, capture_output=True)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_port}"
        self.project = self.post("/api/projects", {"path": str(self.repo), "name": "Fixture"})
        self.provider = self.post("/api/providers", {"kind": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "fixture:1b"})

    def tearDown(self):
        conversations.TRANSPORT = self.old_transport
        self.http.shutdown(); self.http.server_close(); self.thread.join()
        server.STORE.conn.close()
        server.DATA, server.DB_PATH, server.STORE = self.old_data, self.old_db, self.old_store
        self.tmp.cleanup()

    def request(self, method, path, payload=None, headers=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.base + path, data=body, method=method,
                                         headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read() or b"{}")

    def post(self, path, payload=None):
        return self.request("POST", path, payload if payload is not None else {})

    def get(self, path):
        return self.request("GET", path)

    def test_http_conversation_stream_stop_and_delete(self):
        conversation = self.post("/api/conversations", {"project_id": self.project["id"], "provider_id": self.provider["id"]})
        self.assertEqual(conversation["title"], "New conversation")
        sent = self.post(f"/api/conversations/{conversation['id']}/messages", {"content": "hello there"})
        self.assertEqual(sent["status"], "queued")
        mid = sent["assistant_message_id"]
        with urllib.request.urlopen(f"{self.base}/api/conversations/{conversation['id']}/messages/{mid}/stream") as response:
            self.assertEqual(response.headers["Content-Type"], "text/event-stream; charset=utf-8")
            body = response.read().decode()
        self.assertIn("event: token", body)
        self.assertIn("event: done", body)
        self.assertIn('"status": "complete"', body)
        detail = self.get(f"/api/conversations/{conversation['id']}")
        self.assertEqual(detail["conversation"]["messages"][-1]["content"], "Hello world")
        self.assertEqual(detail["streaming"], False)
        renamed = self.request("PATCH", f"/api/conversations/{conversation['id']}", {"title": "Renamed", "pinned": True})
        self.assertEqual(renamed["title"], "Renamed")
        self.assertTrue(renamed["pinned"])
        listing = self.get("/api/conversations")
        self.assertEqual(listing["conversations"][0]["title"], "Renamed")
        self.assertEqual(self.get("/api/conversations/search?q=hello")["results"][0]["conversation_id"], conversation["id"])
        regenerated = self.post(f"/api/conversations/{conversation['id']}/regenerate", {})
        self.assertTrue(regenerated["regenerated"])
        conversations.wait_for_message(server.STORE, regenerated["assistant_message_id"])
        task = self.post(f"/api/conversations/{conversation['id']}/task", {})
        self.assertEqual(task["conversation_id"], conversation["id"])
        self.assertEqual(task["status"], "planned")
        deleted = self.request("DELETE", f"/api/conversations/{conversation['id']}")
        self.assertEqual(deleted["status"], "deleted")
        self.assertEqual(self.get("/api/conversations")["conversations"], [])

    def test_http_stream_can_be_resumed_and_stop_is_reported(self):
        conversations.TRANSPORT = slow_transport()
        conversation = self.post("/api/conversations", {"project_id": self.project["id"], "provider_id": self.provider["id"]})
        sent = self.post(f"/api/conversations/{conversation['id']}/messages", {"content": "keep going"})
        mid = sent["assistant_message_id"]
        with urllib.request.urlopen(f"{self.base}/api/conversations/{conversation['id']}/messages/{mid}/stream") as response:
            lines = []
            for _ in range(6):
                line = response.readline().decode()
                if not line:
                    break
                lines.append(line)
        self.assertTrue(any(line.startswith("event: token") for line in lines))
        stopped = self.post(f"/api/conversations/{conversation['id']}/messages/{mid}/stop", {})
        self.assertTrue(stopped["stopped"])
        final = conversations.wait_for_message(server.STORE, mid)
        self.assertEqual(final["status"], "stopped")
        inactive = self.post(f"/api/conversations/{conversation['id']}/messages/{mid}/stop", {})
        self.assertFalse(inactive["stopped"])

    def test_http_stop_reports_when_no_generation_is_running(self):
        conversation = self.post("/api/conversations", {"project_id": self.project["id"], "provider_id": self.provider["id"]})
        # A row left mid-stream with no worker behind it, as a crash between write and recovery would leave.
        mid = conversations.new_message(server.STORE, conversation["id"], "assistant", "orphan", status="streaming")["id"]
        orphaned = self.post(f"/api/conversations/{conversation['id']}/messages/{mid}/stop", {})
        self.assertFalse(orphaned["stopped"])
        self.assertEqual(orphaned["status"], "streaming")
        self.assertIn("no running generation", orphaned["reason"])
        server.STORE.write("UPDATE messages SET status='stopped' WHERE id=?", (mid,))
        inactive = self.post(f"/api/conversations/{conversation['id']}/messages/{mid}/stop", {})
        self.assertFalse(inactive["stopped"])
        self.assertEqual(inactive["reason"], "message is not active")

    def test_http_validation_and_missing_resources(self):
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.get("/api/conversations/00000000-0000-0000-0000-000000000000")
        self.assertEqual(missing.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as unknown_provider:
            self.post("/api/conversations", {"provider_id": "nope"})
        self.assertEqual(unknown_provider.exception.code, 404)
        conversation = self.post("/api/conversations", {"project_id": self.project["id"]})
        with self.assertRaises(urllib.error.HTTPError) as no_provider:
            self.post(f"/api/conversations/{conversation['id']}/messages", {"content": "hi"})
        self.assertEqual(no_provider.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as empty:
            self.post(f"/api/conversations/{conversation['id']}/messages", {"content": "  ", "provider_id": self.provider["id"]})
        self.assertEqual(empty.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as bad_title:
            self.request("PATCH", f"/api/conversations/{conversation['id']}", {"title": ""})
        self.assertEqual(bad_title.exception.code, 400)

    def test_http_models_are_listed_without_an_invented_model(self):
        listing = self.get("/api/models")
        self.assertEqual(len(listing["providers"]), 1)
        self.assertEqual(listing["providers"][0]["model"], "fixture:1b")
        # No Ollama is listening here, so live discovery must fail closed with a class, not a fake list.
        with self.assertRaises(urllib.error.HTTPError) as unreachable:
            self.get(f"/api/providers/{self.provider['id']}/models")
        self.assertEqual(unreachable.exception.code, 502)
        body = json.loads(unreachable.exception.read())
        self.assertEqual(body["models"], [])
        self.assertEqual(body["failure_class"], "unreachable")


if __name__ == "__main__":
    unittest.main()
