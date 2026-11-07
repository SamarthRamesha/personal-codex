#!/usr/bin/env python3
"""Focused check: the approved provider workflow routed through the local Respan Gateway.

The check needs no provider key and no network: a loopback fixture speaks the OpenAI-compatible
chat-completions API, the Respan Gateway routes Personal Codex's request to it, and the request
travels the app's normal path — register provider → request approval → approve → invoke.

    python3 scripts/gateway_check.py          # human-readable
    python3 scripts/gateway_check.py --json   # machine-readable report

Requires the pinned integration package (wheels only):

    pip install --only-binary=:all: respan-gateway==0.3.0

Exit codes: 0 the routed workflow completed, 2 the gateway package is unavailable or unconfigured,
4 the request failed on the way through the gateway.

This proves routing, approval binding and response validation. It does not prove a real provider
answers: run the app normally with the developer's own keys for that.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.server as server  # noqa: E402
from app import gateway, tools  # noqa: E402

FIXTURE_KEY_VARIABLE = "PERSONAL_CODEX_GATEWAY_FIXTURE_KEY"
FIXTURE_REPLY = ('{"summary":"gateway fixture reply","status":"continue",'
                 '"operations":[{"tool":"list_files","path":"."}]}')
PROMPT = "Reply with one JSON proposal for a bounded file listing."


class FixtureHandler(BaseHTTPRequestHandler):
    """A loopback OpenAI-compatible provider: one chat completion, or an SSE stream of it."""

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        request = json.loads(self.rfile.read(length) or b"{}")
        if request.get("stream") is True:
            frames = [{"choices": [{"index": 0, "delta": {"content": FIXTURE_REPLY}}]},
                      {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]
            body = "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames) + "data: [DONE]\n\n"
            self._send(200, body.encode("utf-8"), "text/event-stream")
            return
        body = json.dumps({"id": "chatcmpl-fixture", "object": "chat.completion", "created": 0,
                           "model": request.get("model"),
                           "choices": [{"index": 0, "finish_reason": "stop",
                                        "message": {"role": "assistant", "content": FIXTURE_REPLY}}],
                           "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        self._send(200, body.encode("utf-8"), "application/json")

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route Personal Codex's provider workflow through the local Respan Gateway.")
    parser.add_argument("--model", default="fixture-model", help="model name the gateway is asked for")
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    return parser


def run(args) -> tuple[int, dict]:
    report = {"gateway_package": gateway.GATEWAY_PACKAGE, "model": args.model, "checks": []}

    def check(name, ok, detail):
        report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})

    fixture = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    fixture_base = f"http://127.0.0.1:{fixture.server_port}/v1"
    # A placeholder for the fixture, never a real credential: the gateway resolves `env:NAME` itself.
    os.environ.setdefault(FIXTURE_KEY_VARIABLE, "fixture-not-a-secret")

    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    old_data, old_db, old_store, old_stream = server.DATA, server.DB_PATH, server.STORE, server.STREAM_PROVIDER
    server.DATA, server.DB_PATH, server.STORE = base / "control-data", base / "control-data" / "check.db", server.Store()
    http = None
    try:
        try:
            session = gateway.start_gateway({"providers": {"fixture": {"vendor": "openai",
                                                                       "base_url": fixture_base,
                                                                       "key": f"env:{FIXTURE_KEY_VARIABLE}"}}})
        except gateway.GatewayUnavailable as error:
            check("gateway started", False, str(error))
            report["next"] = [f"install the pinned package: {gateway.INSTALL_COMMAND}"]
            return 2, report
        check("gateway started", session.url.startswith("http://127.0.0.1:"), f"loopback {session.endpoint}")

        repo = base / "repo"; repo.mkdir()
        for argv in (["git", "init"], ["git", "config", "user.email", "test@example.invalid"],
                     ["git", "config", "user.name", "Test"]):
            subprocess.run(argv, cwd=repo, check=True, capture_output=True)
        (repo / "README.md").write_text("# fixture\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)

        http = ThreadingHTTPServer(("127.0.0.1", 0), server.App)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        app_base = f"http://127.0.0.1:{http.server_port}"

        def request(path, method="GET", data=None):
            body = json.dumps(data).encode() if data is not None else None
            req = Request(app_base + path, data=body, method=method, headers={"Content-Type": "application/json"})
            try:
                with urlopen(req, timeout=30) as response:
                    return response.status, json.loads(response.read())
            except HTTPError as error:
                return error.code, json.loads(error.read())

        status, project = request("/api/projects", "POST", {"name": "gateway-fixture", "path": str(repo)})
        status, provider = request("/api/providers", "POST", {"kind": gateway.GATEWAY_KIND, "model": args.model})
        check("gateway provider registered", status == 201, f"HTTP {status}, kind {gateway.GATEWAY_KIND}")
        if status != 201:
            return 4, report
        status, capabilities = request(f"/api/providers/{provider['id']}/capabilities")
        check("provider stays loopback and approval-gated",
              status == 200 and capabilities["local_gateway"] and capabilities["invocation_requires_approval"],
              f"HTTP {status}, local_gateway={capabilities.get('local_gateway')}")
        status, task = request("/api/tasks", "POST", {"project_id": project["id"], "prompt": "gateway smoke check"})
        task_id = task["id"]
        status, denied = request(f"/api/tasks/{task_id}/invoke", "POST", {"provider_id": provider["id"], "prompt": PROMPT})
        check("invocation needs its own approval", status == 403, f"HTTP {status} before approval")
        status, approval = request(f"/api/tasks/{task_id}/provider-request", "POST", {"provider_id": provider["id"], "prompt": PROMPT})
        check("approval queued", status == 201, f"HTTP {status}, kind {approval.get('kind')}")
        request(f"/api/approvals/{approval['id']}", "PATCH", {"status": "approved"})
        status, invoked = request(f"/api/tasks/{task_id}/invoke", "POST", {"provider_id": provider["id"], "prompt": PROMPT})
        reply = invoked.get("text", "") if status == 200 else ""
        check("routed completion returned", reply == FIXTURE_REPLY, f"HTTP {status}, {len(reply)} bytes")
        if not reply:
            report["next"] = ["check the fixture log and gateway configuration"]
            return 4, report
        parsed = tools.parse_round_proposal(reply)
        check("reply validates as an agent proposal", parsed["status"] == "continue",
              f"status={parsed['status']}, {len(parsed['operations'])} operation(s)")

        server.STREAM_PROVIDER = True
        provider_row = server.provider_row(provider["id"])
        streamed = server.invoke_provider(provider_row, PROMPT, server.round_transport(provider_row))
        check("streaming path keeps the same gateway route", streamed["text"] == FIXTURE_REPLY,
              f"{len(streamed['text'])} streamed bytes")
        report["result"] = {"model": args.model, "response_bytes": len(reply.encode("utf-8")),
                            "gateway_port": int(session.endpoint.rsplit(":", 1)[1].split("/")[0])}
        return 0, report
    finally:
        server.STREAM_PROVIDER = old_stream
        gateway.stop_gateway()
        if http is not None:
            http.shutdown(); http.server_close()
        fixture.shutdown(); fixture.server_close()
        server.STORE.conn.close()
        server.DATA, server.DB_PATH, server.STORE = old_data, old_db, old_store
        tmp.cleanup()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    os.environ["PERSONAL_CODEX_ENABLE_GATEWAY"] = "1"
    code, report = run(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return code
    for entry in report.get("checks", []):
        print(f"[{'ok' if entry['ok'] else 'FAIL'}] {entry['check']}: {entry['detail']}")
    for step in report.get("next", []):
        print(f"next: {step}")
    if report.get("result"):
        print(f"result: {report['result']['model']} routed through the loopback gateway, "
              f"{report['result']['response_bytes']} bytes returned")
    if code == 0:
        print("Gateway check passed. The reply came from the local fixture, not from a hosted provider.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
