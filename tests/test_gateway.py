"""Respan Gateway provider: metadata rules plus routing through the app's approved path."""
import json
import os
import sys
import threading
from unittest.mock import patch
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import app.server as server
from app import gateway, tools
from app.server import invoke_provider, provider_approval_kind, provider_capabilities, provider_invocation_detail, validate_provider_config

try:
    import respan_gateway  # noqa: F401  (the pinned integration package)
    GATEWAY_INSTALLED = True
except ImportError:
    GATEWAY_INSTALLED = False

# Placeholder for the fixture only; the gateway resolves `env:NAME` itself and no real key is used.
FIXTURE_KEY_VARIABLE = "PERSONAL_CODEX_GATEWAY_FIXTURE_KEY"
os.environ.setdefault(FIXTURE_KEY_VARIABLE, "fixture-not-a-secret")
FIXTURE_REPLY = ('{"summary":"gateway fixture reply","status":"continue",'
                 '"operations":[{"tool":"list_files","path":"."}]}')


def fixture_config(base_url):
    """A gateway whose only provider is the loopback fixture, with an env-referenced placeholder key."""
    return {"providers": {"fixture": {"vendor": "openai", "base_url": base_url,
                                      "key": f"env:{FIXTURE_KEY_VARIABLE}"}}}


class GatewayFixture(BaseHTTPRequestHandler):
    """Loopback OpenAI-compatible provider: one chat completion, or an SSE stream of it."""

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        request = json.loads(self.rfile.read(length) or b"{}")
        if request.get("stream") is True:
            frames = [{"choices": [{"index": 0, "delta": {"content": FIXTURE_REPLY}}]},
                      {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]
            self._send("".join(f"data: {json.dumps(frame)}\n\n" for frame in frames) + "data: [DONE]\n\n", "text/event-stream")
            return
        completion = {"id": "chatcmpl-fixture", "object": "chat.completion", "created": 0, "model": request.get("model"),
                      "choices": [{"index": 0, "finish_reason": "stop",
                                   "message": {"role": "assistant", "content": FIXTURE_REPLY}}],
                      "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        self._send(json.dumps(completion), "application/json")

    def _send(self, body, content_type):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class GatewayProviderConfigTests(unittest.TestCase):
    def test_gateway_provider_stores_no_endpoint_secret_or_cloud_consent(self):
        config = validate_provider_config("respan-gateway", "", "fixture-model", "", False)
        self.assertEqual((config["kind"], config["endpoint"], config["secret_ref"], config["cloud_allowed"]),
                         ("respan-gateway", "", "", 0))

    def test_gateway_provider_refuses_endpoint_secret_and_cloud_consent(self):
        for endpoint, secret_ref, cloud_allowed in (("http://127.0.0.1:9999/v1", "", False),
                                                    ("", "PROVIDER_API_KEY", False),
                                                    ("", "", True)):
            with self.assertRaises(ValueError):
                validate_provider_config("respan-gateway", endpoint, "fixture-model", secret_ref, cloud_allowed)

    def test_gateway_requires_network_approval_even_for_loopback_hop(self):
        provider = {"id": "gateway-1", "kind": "respan-gateway", "endpoint": "", "model": "fixture-model", "cloud_allowed": 0}
        self.assertEqual(provider_approval_kind(provider), "network")
        detail = json.loads(provider_invocation_detail("task-1", provider, "hello"))
        self.assertEqual((detail["refs"]["endpoint"], detail["refs"]["cloud_allowed"]), ("", False))
        self.assertNotEqual(detail["refs"], json.loads(provider_invocation_detail("task-1", provider, "changed"))["refs"])
        self.assertTrue(provider_capabilities(provider)["local_gateway"])
        self.assertFalse(provider_capabilities(provider)["supports_tool_calls"])
        self.assertTrue(provider_capabilities(provider)["external_routing_requires_opt_in"])
        self.assertNotIn("no endpoint configured", server.provider_health({**provider, "enabled": 1})["issues"])

    def test_gateway_cannot_run_without_explicit_enablement(self):
        provider={"kind":"respan-gateway"}
        with patch.dict(os.environ, {"PERSONAL_CODEX_ENABLE_GATEWAY":"0"}):
            for resolve in (server.active_provider_transport, server.round_transport):
                with self.assertRaisesRegex(server.ProviderTransportError, "disabled"):
                    resolve(provider)

    def test_missing_gateway_package_names_the_install_command(self):
        original = sys.modules.get("respan_gateway")
        sys.modules["respan_gateway"] = None
        try:
            with self.assertRaises(gateway.GatewayUnavailable) as caught:
                gateway.LocalGateway()
        finally:
            if original is None:
                sys.modules.pop("respan_gateway", None)
            else:
                sys.modules["respan_gateway"] = original
        self.assertIn("respan-gateway==0.3.0", str(caught.exception))
        self.assertIn("--only-binary=:all:", str(caught.exception))


@unittest.skipUnless(GATEWAY_INSTALLED, "requires the pinned respan-gateway package")
class GatewayRoutingTests(unittest.TestCase):
    """The provider workflow reaches a loopback fixture only through the gateway."""

    def setUp(self):
        self.gateway_policy = patch.dict(os.environ, {"PERSONAL_CODEX_ENABLE_GATEWAY":"1"})
        self.gateway_policy.start()
        self.addCleanup(self.gateway_policy.stop)
        self.fixture = ThreadingHTTPServer(("127.0.0.1", 0), GatewayFixture)
        threading.Thread(target=self.fixture.serve_forever, daemon=True).start()
        self.old_stream = server.STREAM_PROVIDER
        self.session = gateway.start_gateway(fixture_config(f"http://127.0.0.1:{self.fixture.server_port}/v1"))
        self.provider = {"id": "gateway-1", "kind": "respan-gateway", "endpoint": "", "model": "fixture-model", "cloud_allowed": 0}

    def tearDown(self):
        server.STREAM_PROVIDER = self.old_stream
        gateway.stop_gateway()
        self.fixture.shutdown()
        self.fixture.server_close()

    def test_approved_invocation_routes_through_the_loopback_gateway(self):
        self.assertTrue(self.session.endpoint.startswith("http://127.0.0.1:"))
        self.assertEqual(self.session.endpoint, f"{gateway.active_gateway().url}/v1")
        result = invoke_provider(self.provider, "hello", server.active_provider_transport(self.provider))
        self.assertEqual(result["text"], FIXTURE_REPLY)
        self.assertEqual(tools.parse_round_proposal(result["text"])["status"], "continue")

    def test_streaming_round_keeps_the_gateway_route(self):
        server.STREAM_PROVIDER = True
        result = invoke_provider(self.provider, "hello", server.round_transport(self.provider))
        self.assertEqual(result["text"], FIXTURE_REPLY)

    def test_gateway_is_loopback_only(self):
        self.assertTrue(self.session.url.startswith("http://127.0.0.1:"))
        self.assertNotIn("0.0.0.0", self.session.url)


if __name__ == "__main__":
    unittest.main()
