"""Provider adapter tests against a disposable loopback stub server.

No real model and no external network are used: every request goes to an ephemeral
127.0.0.1 listener created by the test.
"""
import json
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import app.server as server
from app.providers import OllamaTransport, ProviderTransportError, openai_transport, post_json, transport_for


def start_stub(status=200, payload=b"{}", delay=0.0):
    recorded = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) or b"{}"
            recorded.append({"path": self.path, "body": json.loads(raw), "headers": dict(self.headers)})
            if delay:
                time.sleep(delay)
            self.send_response(status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except OSError:  # client timed out on purpose
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{httpd.server_port}", recorded, thread


def stop_stub(httpd, thread):
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def dead_loopback_url():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return f"http://127.0.0.1:{port}"


class OllamaTransportTests(unittest.TestCase):
    def test_chat_request_uses_model_prompt_and_exact_path(self):
        httpd, url, recorded, thread = start_stub(payload=json.dumps({"message": {"role": "assistant", "content": "local answer"}}).encode())
        try:
            result = OllamaTransport()({"kind": "ollama", "endpoint": url, "model": "qwen", "prompt": "hello", "cloud_allowed": False})
        finally:
            stop_stub(httpd, thread)
        self.assertEqual(result["text"], "local answer")
        self.assertEqual(recorded[0]["path"], "/api/chat")
        self.assertEqual(recorded[0]["body"], {"model": "qwen", "messages": [{"role": "user", "content": "hello"}], "stream": False})

    def test_generate_endpoint_shape_and_response(self):
        httpd, url, recorded, thread = start_stub(payload=json.dumps({"response": "generated"}).encode())
        try:
            result = OllamaTransport()({"kind": "ollama", "endpoint": url + "/api/generate", "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertEqual((result["text"], recorded[0]["path"]), ("generated", "/api/generate"))
        self.assertEqual(recorded[0]["body"]["prompt"], "p")

    def test_malformed_json_is_reported_without_leaking_body(self):
        httpd, url, _, thread = start_stub(payload=b"<html>not json</html>")
        try:
            with self.assertRaises(ProviderTransportError) as caught:
                OllamaTransport()({"endpoint": url, "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertIn("malformed JSON", str(caught.exception))

    def test_http_error_is_mapped_and_bounded(self):
        httpd, url, _, thread = start_stub(status=500, payload=b'{"error":"model not found"}')
        try:
            with self.assertRaises(ProviderTransportError) as caught:
                OllamaTransport()({"endpoint": url, "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertIn("HTTP 500", str(caught.exception))
        self.assertLessEqual(len(str(caught.exception)), 400)

    def test_redirect_is_refused(self):
        httpd, url, _, thread = start_stub(status=302, payload=b"")
        try:
            with self.assertRaises(ProviderTransportError) as caught:
                OllamaTransport()({"endpoint": url, "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertIn("redirects are not permitted", str(caught.exception))

    def test_connection_refused_is_reported(self):
        with self.assertRaises(ProviderTransportError) as caught:
            OllamaTransport(timeout=2)({"endpoint": dead_loopback_url(), "model": "m", "prompt": "p"})
        self.assertIn("connection failed", str(caught.exception).lower())

    def test_timeout_is_reported(self):
        httpd, url, _, thread = start_stub(payload=b"{}", delay=1.0)
        try:
            with self.assertRaises(ProviderTransportError) as caught:
                OllamaTransport(timeout=0.2)({"endpoint": url, "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertIn("connection failed", str(caught.exception).lower())

    def test_oversized_response_is_refused(self):
        httpd, url, _, thread = start_stub(payload=json.dumps({"message": {"content": "x" * 5000}}).encode())
        try:
            with self.assertRaises(ProviderTransportError) as caught:
                OllamaTransport(max_bytes=256)({"endpoint": url, "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertIn("size limit", str(caught.exception))

    def test_unexpected_structure_is_refused(self):
        httpd, url, _, thread = start_stub(payload=b'{"done":true}')
        try:
            with self.assertRaises(ProviderTransportError) as caught:
                OllamaTransport()({"endpoint": url, "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertIn("did not contain assistant text", str(caught.exception))

    def test_invalid_endpoints_are_refused_before_any_connection(self):
        for endpoint in ("ftp://127.0.0.1/model", "http://user:pass@127.0.0.1:1", "not-a-url", ""):
            with self.assertRaises(ProviderTransportError):
                OllamaTransport()({"endpoint": endpoint, "model": "m", "prompt": "p"})

    def test_non_loopback_endpoint_is_refused_for_a_local_provider(self):
        with self.assertRaises(ProviderTransportError) as caught:
            post_json("http://provider.example:11434", "/api/chat", {}, timeout=1)
        self.assertIn("non-loopback", str(caught.exception))


class OpenAICompatibleTransportTests(unittest.TestCase):
    def test_chat_completions_request_and_authorization_header(self):
        payload = json.dumps({"choices": [{"message": {"role": "assistant", "content": "remote-shaped answer"}}]}).encode()
        httpd, url, recorded, thread = start_stub(payload=payload)
        try:
            transport = openai_transport("PROVIDER_API_KEY", secret_reader=lambda name: "test-credential")
            result = transport({"kind": "openai-compatible", "endpoint": url + "/v1", "model": "gpt-local", "prompt": "hi", "cloud_allowed": False})
        finally:
            stop_stub(httpd, thread)
        self.assertEqual(result["text"], "remote-shaped answer")
        self.assertEqual(recorded[0]["path"], "/v1/chat/completions")
        self.assertEqual(recorded[0]["body"]["model"], "gpt-local")
        self.assertEqual(recorded[0]["headers"]["Authorization"], "Bearer test-credential")
        self.assertNotIn("test-credential", json.dumps(result))

    def test_missing_credential_fails_before_any_request(self):
        httpd, url, recorded, thread = start_stub(payload=b"{}")
        try:
            transport = openai_transport("PROVIDER_API_KEY", secret_reader=lambda name: None)
            with self.assertRaises(ProviderTransportError) as caught:
                transport({"endpoint": url + "/v1", "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertIn("credential is unavailable", str(caught.exception))
        self.assertEqual(recorded, [])

    def test_cloud_provider_requires_a_secret_reference(self):
        with self.assertRaises(ProviderTransportError) as caught:
            openai_transport("")({"endpoint": "https://provider.example/v1", "model": "m", "prompt": "p", "cloud_allowed": True})
        self.assertIn("secret reference", str(caught.exception))

    def test_missing_choice_is_refused(self):
        httpd, url, _, thread = start_stub(payload=b'{"choices":[]}')
        try:
            with self.assertRaises(ProviderTransportError) as caught:
                openai_transport()({"endpoint": url + "/v1", "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertIn("completion choice", str(caught.exception))

    def test_loopback_provider_without_secret_sends_no_authorization_header(self):
        payload = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        httpd, url, recorded, thread = start_stub(payload=payload)
        try:
            openai_transport()({"endpoint": url, "model": "m", "prompt": "p"})
        finally:
            stop_stub(httpd, thread)
        self.assertNotIn("Authorization", recorded[0]["headers"])


class ProviderApiIntegrationTests(unittest.TestCase):
    """Opt-in: the real built-in transport through the HTTP API, no override."""

    @unittest.skipUnless(__import__("os").getenv("PERSONAL_CODEX_HTTP_TESTS") == "1", "requires an explicitly enabled loopback listener")
    def test_approved_invocation_reaches_the_builtin_adapter_and_ledger(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        httpd, url, recorded, thread = start_stub(payload=json.dumps({"message": {"content": "stub model reply"}}).encode())
        tmp = tempfile.TemporaryDirectory()
        base = Path(tmp.name)
        old = (server.DATA, server.DB_PATH, server.STORE, server.PROVIDER_TRANSPORT)
        server.DATA, server.DB_PATH, server.STORE = base / "control-data", base / "control-data" / "test.db", server.Store()
        app_server = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        app_thread = threading.Thread(target=app_server.serve_forever, daemon=True)
        app_thread.start()
        root = f"http://127.0.0.1:{app_server.server_port}"

        def call(path, method="GET", data=None):
            body = json.dumps(data).encode() if data is not None else None
            request = Request(root + path, data=body, method=method, headers={"Content-Type": "application/json"})
            try:
                with urlopen(request, timeout=5) as response:
                    return response.status, json.loads(response.read())
            except HTTPError as error:
                return error.code, json.loads(error.read())

        repo = base / "repo"
        repo.mkdir()
        for args in (["git", "init"], ["git", "config", "user.email", "t@example.invalid"], ["git", "config", "user.name", "T"]):
            subprocess.run(args, cwd=repo, check=True, capture_output=True)
        (repo / "README.md").write_text("# fixture\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        try:
            status, project = call("/api/projects", "POST", {"name": "fixture", "path": str(repo)})
            self.assertEqual(status, 201)
            status, provider = call("/api/providers", "POST", {"kind": "ollama", "endpoint": url, "model": "stub-model"})
            self.assertEqual(status, 201)
            status, task = call("/api/tasks", "POST", {"project_id": project["id"], "prompt": "integration"})
            self.assertEqual(status, 201)
            task_id = task["id"]
            status, _ = call(f"/api/tasks/{task_id}/invoke", "POST", {"provider_id": provider["id"], "prompt": "hello"})
            self.assertEqual(status, 403)
            status, approval = call(f"/api/tasks/{task_id}/provider-request", "POST", {"provider_id": provider["id"], "prompt": "hello"})
            self.assertEqual(status, 201)
            self.assertEqual(call(f"/api/approvals/{approval['id']}", "PATCH", {"status": "approved"})[0], 200)
            status, result = call(f"/api/tasks/{task_id}/invoke", "POST", {"provider_id": provider["id"], "prompt": "hello"})
            self.assertEqual(status, 200)
            self.assertEqual(result["text"], "stub model reply")
            self.assertEqual(recorded[0]["path"], "/api/chat")
            self.assertEqual(recorded[0]["body"]["model"], "stub-model")
            status, ledger = call(f"/api/tasks/{task_id}/invocations")
            self.assertEqual((status, len(ledger)), (200, 1))
            self.assertIn("stub model reply", ledger[0]["response"])
        finally:
            app_server.shutdown()
            app_server.server_close()
            app_thread.join()
            server.STORE.conn.close()
            server.DATA, server.DB_PATH, server.STORE, server.PROVIDER_TRANSPORT = old
            stop_stub(httpd, thread)
            tmp.cleanup()


class TransportSelectionTests(unittest.TestCase):
    def test_unknown_kind_has_no_transport(self):
        with self.assertRaises(ProviderTransportError):
            transport_for({"kind": "mystery"})

    def test_default_override_is_none_and_unsupported_kind_fails_closed(self):
        self.assertIsNone(server.PROVIDER_TRANSPORT)
        with self.assertRaises(ProviderTransportError):
            server.active_provider_transport({"kind": "mystery", "secret_ref": ""})

    def test_injected_transport_override_wins(self):
        provider = {"kind": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "m", "cloud_allowed": 0}
        server.PROVIDER_TRANSPORT = lambda request: {"text": "stub"}
        try:
            self.assertEqual(server.active_provider_transport(provider)({"prompt": "x"})["text"], "stub")
        finally:
            server.PROVIDER_TRANSPORT = None


if __name__ == "__main__":
    unittest.main()
