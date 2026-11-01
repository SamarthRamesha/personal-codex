"""Streaming transport, model discovery, error redaction and the live diagnostic harness.

Every test uses an ephemeral loopback stub; no real model and no external network are involved.
"""
import contextlib
import importlib.util
import io
import json
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.providers import (OllamaStreamTransport, ProviderTransportError, discover_models, get_json,
                           redact_provider_text)

ROOT = Path(__file__).resolve().parents[1]


def load_harness():
    spec = importlib.util.spec_from_file_location("live_provider_check", ROOT / "scripts" / "live_provider_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StreamStub:
    """Loopback stub serving `/api/tags` and a configurable NDJSON chat stream."""

    def __init__(self, chunks=None, status=200, models=None, malformed=False, delay=0.0):
        self.chunks = chunks if chunks is not None else []
        self.status, self.models, self.malformed, self.delay = status, models or [], malformed, delay
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps({"models": [{"name": name} for name in outer.models]}).encode()
                self.send_response(outer.status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) or b"{}"
                outer.requests.append({"path": self.path, "body": json.loads(raw), "headers": dict(self.headers)})
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                if outer.delay:
                    import time
                    time.sleep(outer.delay)
                if outer.malformed:
                    self.wfile.write(b"not json\n")
                try:
                    for chunk in outer.chunks:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except OSError:
                    pass
                self.close_connection = True

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()


def line(text, done=False):
    return (json.dumps({"message": {"role": "assistant", "content": text}, "done": done}) + "\n").encode()


class StreamingTransportTests(unittest.TestCase):
    def test_stream_accumulates_chunks_until_done(self):
        stub = StreamStub([line('{"summary":"x",'), line('"status":"continue",'), line('"operations":[]}', True)])
        try:
            result = OllamaStreamTransport()({"endpoint": stub.url, "model": "m", "prompt": "p"})
        finally:
            stub.stop()
        self.assertEqual(result["text"], '{"summary":"x","status":"continue","operations":[]}')
        self.assertTrue(result["streamed"])

    def test_stream_without_done_marker_is_rejected(self):
        stub = StreamStub([line('{"partial":true}')])
        try:
            with self.assertRaises(ProviderTransportError) as raised:
                OllamaStreamTransport()({"endpoint": stub.url, "model": "m", "prompt": "p"})
        finally:
            stub.stop()
        self.assertIn("completion marker", str(raised.exception))

    def test_malformed_chunk_is_rejected(self):
        stub = StreamStub(malformed=True)
        try:
            with self.assertRaises(ProviderTransportError) as raised:
                OllamaStreamTransport()({"endpoint": stub.url, "model": "m", "prompt": "p"})
        finally:
            stub.stop()
        self.assertIn("malformed", str(raised.exception))

    def test_oversized_stream_is_bounded(self):
        stub = StreamStub([line("x" * 500), line("y", True)])
        try:
            with self.assertRaises(ProviderTransportError):
                OllamaStreamTransport(max_bytes=100)({"endpoint": stub.url, "model": "m", "prompt": "p"})
        finally:
            stub.stop()

    def test_cancellation_stops_the_stream(self):
        stub = StreamStub([line("a"), line("b"), line("c", True)])
        counts = []
        try:
            with self.assertRaises(ProviderTransportError) as raised:
                OllamaStreamTransport()({"endpoint": stub.url, "model": "m", "prompt": "p",
                                         "stop_check": lambda: True, "on_chunk": counts.append})
        finally:
            stub.stop()
        self.assertIn("cancelled", str(raised.exception))

    def test_http_error_stream_is_sanitised(self):
        stub = StreamStub(status=401)
        try:
            with self.assertRaises(ProviderTransportError) as raised:
                OllamaStreamTransport()({"endpoint": stub.url, "model": "m", "prompt": "p"})
        finally:
            stub.stop()
        self.assertIn("401", str(raised.exception))

    def test_non_loopback_endpoint_is_refused(self):
        with self.assertRaises(ProviderTransportError):
            OllamaStreamTransport()({"endpoint": "http://example.com:11434", "model": "m", "prompt": "p"})


class DiscoveryAndRedactionTests(unittest.TestCase):
    def test_models_are_discovered_and_bounded(self):
        stub = StreamStub(models=["qwen2.5-coder:7b", "llama3.2:3b"])
        try:
            models = discover_models(stub.url)
        finally:
            stub.stop()
        self.assertEqual(models, ["qwen2.5-coder:7b", "llama3.2:3b"])

    def test_discovery_refuses_non_loopback_without_consent(self):
        with self.assertRaises(ProviderTransportError):
            discover_models("http://203.0.113.9:11434")

    def test_discovery_reports_provider_errors_without_echoing_secrets(self):
        secret = "sk-live-abcdefghijklmnop"
        stub = StreamStub(status=401)
        try:
            with self.assertRaises(ProviderTransportError) as raised:
                get_json(stub.url, "/api/tags")
        finally:
            stub.stop()
        self.assertNotIn(secret, str(raised.exception))

    def test_redaction_scrubs_secret_shapes(self):
        text = redact_provider_text('{"error":"bad key sk-live-abcdefghijklmnop","api_key":"value123"}')
        self.assertNotIn("sk-live-abcdefghijklmnop", text)
        self.assertIn("[redacted]", text)


class LiveHarnessTests(unittest.TestCase):
    """The diagnostic harness must be deterministic and honest without a live model."""

    def run_harness(self, args):
        harness = load_harness()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = harness.main(args)
        return code, buffer.getvalue()

    def test_missing_service_reports_failure(self):
        probe = socket.socket(); probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]; probe.close()
        code, output = self.run_harness(["--endpoint", f"http://127.0.0.1:{port}", "--timeout", "1", "--json"])
        self.assertEqual(code, 4, output)
        self.assertIn("service reachable", output)

    def test_no_installed_models_is_reported(self):
        stub = StreamStub(models=[])
        try:
            code, output = self.run_harness(["--endpoint", stub.url, "--discover-models", "--json"])
        finally:
            stub.stop()
        self.assertEqual(code, 2, output)
        self.assertIn("no installed models", output)

    def test_model_must_be_selected_explicitly(self):
        stub = StreamStub(models=["some-model"], chunks=[line('{"summary":"x","status":"continue","operations":[]}', True)])
        try:
            code, output = self.run_harness(["--endpoint", stub.url, "--json"])
        finally:
            stub.stop()
        self.assertEqual(code, 2, output)
        self.assertIn("explicitly", output)

    def test_valid_model_answer_passes_schema_probe(self):
        stub = StreamStub(models=["some-model"], chunks=[line(
            '{"summary":"ok","status":"continue","operations":[{"tool":"list_files","path":"."}]}', True)])
        try:
            code, output = self.run_harness(["--endpoint", stub.url, "--model", "some-model", "--json"])
        finally:
            stub.stop()
        report = json.loads(output)
        self.assertEqual(code, 0, output)
        self.assertEqual(report["proposal"]["operations"], 1)
        self.assertIn("latency_ms", report)

    def test_invalid_json_answer_fails_schema_check(self):
        stub = StreamStub(models=["some-model"], chunks=[line("I cannot do that.", True)])
        try:
            code, output = self.run_harness(["--endpoint", stub.url, "--model", "some-model", "--json"])
        finally:
            stub.stop()
        self.assertEqual(code, 3, output)
        self.assertIn("proposal schema", output)


if __name__ == "__main__":
    unittest.main()


class OpenAIStreamingTests(unittest.TestCase):
    def start_sse(self, frames, status=200, done=True):
        rows = [("data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}) + "\n\n").encode() for piece in frames]
        if done:
            rows.append(b"data: [DONE]\n\n")

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                self.send_response(status)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                try:
                    for row in rows:
                        self.wfile.write(row)
                    self.close_connection = True
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return httpd, thread, f"http://127.0.0.1:{httpd.server_port}"

    def stop(self, httpd, thread):
        httpd.shutdown(); httpd.server_close(); thread.join()

    def test_sse_frames_are_joined_until_done(self):
        from app.providers import OpenAIStreamTransport
        httpd, thread, url = self.start_sse(['{"a":', '1}'])
        try:
            result = OpenAIStreamTransport()({"endpoint": url, "model": "m", "prompt": "p"})
        finally:
            self.stop(httpd, thread)
        self.assertEqual(result["text"], '{"a":1}')

    def test_unterminated_sse_stream_is_rejected(self):
        from app.providers import OpenAIStreamTransport
        httpd, thread, url = self.start_sse(['{"a":1}'], done=False)
        try:
            with self.assertRaises(ProviderTransportError) as raised:
                OpenAIStreamTransport()({"endpoint": url, "model": "m", "prompt": "p"})
        finally:
            self.stop(httpd, thread)
        self.assertIn("termination frame", str(raised.exception))

    def test_malformed_sse_frame_is_rejected(self):
        from app.providers import OpenAIStreamTransport

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"data: not-json\n\ndata: [DONE]\n\n")
                self.close_connection = True

            def log_message(self, *args):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(ProviderTransportError) as raised:
                OpenAIStreamTransport()({"endpoint": f"http://127.0.0.1:{httpd.server_port}", "model": "m", "prompt": "p"})
        finally:
            httpd.shutdown(); httpd.server_close(); thread.join()
        self.assertIn("malformed", str(raised.exception))

    def test_missing_credential_fails_before_any_request(self):
        from app.providers import OpenAIStreamTransport
        with self.assertRaises(ProviderTransportError) as raised:
            OpenAIStreamTransport("MISSING_KEY", secret_reader=lambda name: "")({
                "endpoint": "http://127.0.0.1:1", "model": "m", "prompt": "p"})
        self.assertIn("credential", str(raised.exception))


class FailureClassificationTests(unittest.TestCase):
    def test_error_classes_are_stable(self):
        from app.providers import ProviderTransportError as PTE, classify_provider_error as classify
        self.assertEqual(classify(PTE("Provider connection failed: ConnectionRefusedError")), "unreachable")
        self.assertEqual(classify(PTE("Provider returned HTTP 401: nope")), "unauthorised")
        self.assertEqual(classify(PTE("Provider response exceeded the size limit")), "oversized")
        self.assertEqual(classify(PTE("Provider returned a malformed streaming chunk")), "malformed")
        self.assertEqual(classify(PTE("Provider redirects are not permitted")), "redirect")
        self.assertEqual(classify(PTE("something else")), "provider-error")

    def test_discovery_retries_only_unreachable_failures(self):
        from app.providers import discover_models_retrying
        import socket
        probe = socket.socket(); probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]; probe.close()
        with self.assertRaises(ProviderTransportError):
            discover_models_retrying(f"http://127.0.0.1:{port}", timeout=0.5, attempts=2)
