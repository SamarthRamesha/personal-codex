"""Reported model properties and observed timings never authorize inference."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from app import model_observations as observations, providers, security, server


class ResponseStub:
    def __init__(self, body, content_type="application/json"):
        self.requests = []
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                outer.requests.append(json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0")))))
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.url = f"http://127.0.0.1:{self.http.server_port}"
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *args):
        self.http.shutdown(); self.http.server_close(); self.thread.join(timeout=3)


class ModelObservationTests(unittest.TestCase):
    def setUp(self):
        settings = patch.dict(os.environ, {"PERSONAL_CODEX_INFERENCE_POLICY": "development"})
        settings.start(); self.addCleanup(settings.stop)

    def test_catalog_has_attribution_and_does_not_guess_capabilities_or_memory_fit(self):
        row = observations.model_catalog([{"name": "local:9b", "size": 1234, "digest": "a"*64,
               "details": {"format": "gguf", "family": "qwen", "parameter_size": "9B", "quantization_level": "Q4_K_M"},
               "prompt": "must not copy", "capabilities": ["tools"]}])[0]
        self.assertEqual((row["size_bytes"], row["quantization"], row["metadata_source"]), (1234, "Q4_K_M", "ollama-tags"))
        for field in ("context_length", "tool_calls", "vision"):
            self.assertIsNone(row[field])
        self.assertEqual(row["hardware_fit"], "unmeasured")
        self.assertNotIn("must not copy", json.dumps(row))

    def test_catalog_rejects_ambiguous_names_invalid_sizes_and_duplicate_aliases(self):
        rows = observations.model_catalog([None, {"name": "bad\nname"}, {"name": "bad\u202ename"},
               {"name": "x"*121}, {"name": " local "}, {"name": "local", "size": True},
               {"name": "local", "size": 1}, {"name": "other", "size": -1, "digest": "mutable"}])
        self.assertEqual([row["name"] for row in rows], ["local", "other"])
        self.assertIsNone(rows[0]["size_bytes"])
        self.assertIsNone(rows[1]["digest"])

    def test_catalog_is_bounded(self):
        self.assertEqual(len(observations.model_catalog([{"name": f"local:{i}"} for i in range(1001)])), 200)
        self.assertEqual(observations.model_catalog("invalid"), [])

    def test_discovery_keeps_legacy_names_and_reads_only_tags(self):
        reply = {"models": [{"name": "local:1b"}]}
        with patch.object(providers, "get_json", return_value=reply) as get:
            self.assertEqual(providers.discover_models("http://127.0.0.1:11434/base/api/chat"), ["local:1b"])
            self.assertEqual(get.call_args.args, ("http://127.0.0.1:11434/base/api/chat", "/base/api/tags"))
        with patch.object(providers, "get_json", return_value={"models": "invalid"}):
            with self.assertRaises(providers.ProviderTransportError):
                providers.discover_model_catalog("http://127.0.0.1:11434")

    def test_new_discovery_path_does_not_bypass_network_consent(self):
        with self.assertRaises(providers.ProviderTransportError):
            providers.discover_model_catalog("http://203.0.113.9:11434")

    def test_usage_counts_and_throughput_are_explicitly_provider_reported(self):
        result = observations.reported_usage({"prompt_eval_count": 30, "eval_count": 10, "eval_duration": 2_000_000_000})
        self.assertEqual(result, {"input_tokens": 30, "output_tokens": 10, "generation_ns": 2_000_000_000, "tokens_per_second": 5.0})
        self.assertNotIn("tokens_per_second", observations.reported_usage({"eval_count": 10, "eval_duration": 0}))
        self.assertEqual(observations.reported_usage({}), {})

    def test_invalid_and_huge_numbers_cannot_create_metrics(self):
        for value in (True, -1, "12", float("nan"), float("inf"), 10**1000):
            with self.subTest(value=type(value).__name__):
                self.assertEqual(observations.reported_usage({"eval_count": value}), {})
                self.assertIsNone(observations.number(value, 1000))

    def test_client_timing_is_measured_and_unknown_counts_remain_unknown(self):
        with patch.object(observations.time, "monotonic", return_value=12):
            result = observations.completed(10, 11)
        self.assertEqual(result, {"client_duration_ms": 2000, "first_text_ms": 1000, "provider_reported": {}})

    def test_whitelist_drops_payload_strings_and_recomputes_caller_duration(self):
        with patch.object(observations.time, "monotonic", return_value=12):
            result = observations.invocation_metrics({"client_duration_ms": -1, "first_text_ms": 999999,
                "prompt": "SYNTHETIC_PRIVATE", "provider_reported": {"output_tokens": 10, "generation_ns": 2_000_000_000,
                "tokens_per_second": 9999, "token": "SYNTHETIC_PRIVATE"}}, 10)
        self.assertEqual(result["client_duration_ms"], 2000)
        self.assertIsNone(result["first_text_ms"])
        self.assertEqual(result["provider_reported"]["tokens_per_second"], 5.0)
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))

    def test_invocation_seam_returns_safe_observations_without_extra_content(self):
        provider = {"id": "synthetic", "kind": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "local", "cloud_allowed": False}
        result = server.invoke_provider(provider, "synthetic prompt", lambda request: {"text": "ok",
                    "metrics": {"prompt": "SYNTHETIC_PRIVATE", "provider_reported": {"input_tokens": 3}}})
        self.assertEqual(result["text"], "ok")
        self.assertEqual(result["metrics"]["provider_reported"], {"input_tokens": 3})
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))

    def test_ollama_nonstream_has_counts_but_does_not_invent_first_text_time(self):
        reply = {"message": {"content": "ok"}, "eval_count": 4, "eval_duration": 1_000_000_000}
        with patch.object(providers, "post_json", return_value=reply):
            result = providers.OllamaTransport()({"endpoint": "http://127.0.0.1:11434", "model": "local", "prompt": "p"})
        self.assertIsNone(result["metrics"]["first_text_ms"])
        self.assertEqual(result["metrics"]["provider_reported"]["tokens_per_second"], 4.0)

    def test_ollama_stream_has_observed_first_text_and_terminal_usage(self):
        body = (json.dumps({"message": {"content": "ok"}, "done": False}) + "\n" +
                json.dumps({"done": True, "eval_count": 4, "eval_duration": 1_000_000_000}) + "\n").encode()
        with ResponseStub(body, "application/x-ndjson") as stub:
            result = providers.OllamaStreamTransport()({"endpoint": stub.url, "model": "local", "prompt": "p"})
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["first_text_ms"], 0)
        self.assertLessEqual(metrics["first_text_ms"], metrics["client_duration_ms"])
        self.assertEqual(metrics["provider_reported"]["output_tokens"], 4)

    def test_openai_nonstream_reports_only_available_counts(self):
        reply = {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 4}}
        with patch.object(providers, "post_json", return_value=reply):
            result = providers.openai_transport()({"endpoint": "http://127.0.0.1:9000", "model": "local", "prompt": "p"})
        self.assertEqual(result["metrics"]["provider_reported"], {"input_tokens": 3, "output_tokens": 4})

    def test_openai_stream_keeps_usage_and_does_not_guess_throughput(self):
        entries = [{"choices": [{"delta": {"content": "ok"}}]}, {"choices": [], "usage": {"completion_tokens": 4}}]
        body = ("".join("data: " + json.dumps(item) + "\n\n" for item in entries) + "data: [DONE]\n\n").encode()
        with ResponseStub(body, "text/event-stream") as stub:
            result = providers.OpenAIStreamTransport()({"endpoint": stub.url, "model": "local", "prompt": "p"})
        self.assertIsNotNone(result["metrics"]["first_text_ms"])
        self.assertEqual(result["metrics"]["provider_reported"], {"output_tokens": 4})

    def test_usage_frame_does_not_make_an_unterminated_stream_successful(self):
        body = b'data: {"choices":[{"delta":{"content":"partial"}}],"usage":{"completion_tokens":4}}\n\n'
        with ResponseStub(body, "text/event-stream") as stub:
            with self.assertRaises(providers.ProviderTransportError):
                providers.OpenAIStreamTransport()({"endpoint": stub.url, "model": "local", "prompt": "p"})


class CatalogApiTests(unittest.TestCase):
    def test_offline_catalog_filters_models_without_inference_or_task_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = server.DATA, server.DB_PATH, server.STORE, server.AUTH
            server.DATA, server.DB_PATH = root / "state", root / "state/db.sqlite3"
            server.STORE = server.Store(); server.AUTH = security.OwnerAuth("synthetic-catalog-owner-000000000000")
            http = None
            try:
                with patch.dict(os.environ, {"PERSONAL_CODEX_INFERENCE_POLICY": "offline"}):
                    server.seed_offline_providers()
                    http = server.runtime.ControlServer(("127.0.0.1", 0), server.App)
                    thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
                    connection = HTTPConnection("127.0.0.1", http.server_port, timeout=5)
                    try:
                        with patch.object(providers, "get_json", return_value={"models": [{"name": "qwen3.5:9b"}, {"name": "unapproved-model"}]}):
                            connection.request("GET", "/api/providers/offline-ollama-qwen3.5:9b/models",
                                               headers={"Authorization": "Bearer synthetic-catalog-owner-000000000000"})
                            response = connection.getresponse(); body = json.load(response)
                        self.assertEqual(response.status, 200, body)
                        self.assertEqual(body["models"], ["qwen3.5:9b"])
                        self.assertEqual([row["name"] for row in body["catalog"]], body["models"])
                        self.assertNotIn("unapproved-model", json.dumps(body))
                        self.assertEqual(body["configured_context_length"], 8192)
                        self.assertEqual(body["selection_policy"], "explicit-only")
                        self.assertEqual(server.STORE.one("SELECT COUNT(*) AS n FROM invocations")["n"], 0)
                    finally:
                        connection.close()
            finally:
                if http:
                    http.shutdown(); http.server_close(); thread.join(timeout=3)
                server.STORE.conn.close()
                server.DATA, server.DB_PATH, server.STORE, server.AUTH = old


if __name__ == "__main__":
    unittest.main()
