#!/usr/bin/env python3
"""Read-only live provider diagnostic for Personal Codex.

This is the only component that is meant to contact a real model, and it only does so when a human runs
it explicitly. It never registers a project, never creates a worktree, never writes a file, and never
sends anything to a non-loopback host unless the endpoint is explicitly marked as cloud-consented.

Typical use on the owner's Mac:

    python3 scripts/live_provider_check.py --discover-models
    python3 scripts/live_provider_check.py --model qwen2.5-coder:7b

Exit codes: 0 diagnostic passed, 2 no usable model, 3 the model did not return a valid proposal,
4 the provider failed (unreachable, timeout, HTTP error).

Nothing here stops the approval-gated product flow from being the only path that edits code.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import providers, tools  # noqa: E402

PROBE_PROMPT = (
    "Reply with JSON only, no prose, in exactly this shape: "
    '{"summary":"one short sentence","status":"continue","operations":[{"tool":"list_files","path":"."}]}'
)
MAX_REPORTED_BYTES = 10_000_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose a local Ollama provider without modifying anything.")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434", help="loopback Ollama endpoint")
    parser.add_argument("--model", default="", help="explicitly installed model name (never guessed)")
    parser.add_argument("--discover-models", action="store_true", help="list locally installed models and exit")
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds for the probe request")
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    parser.add_argument("--cloud-allowed", action="store_true", help="acknowledge a non-loopback endpoint")
    return parser


def run(args) -> tuple[int, dict]:
    report = {"endpoint": args.endpoint, "model": args.model or None, "checks": []}

    def check(name, ok, detail):
        report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})

    try:
        models = providers.discover_models_retrying(args.endpoint, timeout=min(args.timeout, 10.0), cloud_allowed=args.cloud_allowed)
    except providers.ProviderTransportError as error:
        check("service reachable", False, providers.redact_provider_text(str(error)))
        report["failure_class"] = providers.classify_provider_error(error)
        report["models"] = []
        return 4, report
    report["models"] = models
    check("service reachable", True, f"{len(models)} installed model(s)")

    if args.discover_models:
        if not models:
            check("model available", False, "no installed models; run `ollama pull <model>` on the owner's machine")
        else:
            check("model available", True, "run again with --model <name> to probe a chosen model")
        return (0 if models else 2), report

    if not models:
        check("model available", False, "no installed models; run `ollama pull <model>` on the owner's machine")
        return 2, report
    if not args.model:
        check("model available", False, "select one explicitly with --model (installed models are listed above)")
        return 2, report
    check("model available", args.model in models, f"{args.model} {'is' if args.model in models else 'is NOT'} installed")

    started = time.time()
    try:
        reply = providers.OllamaTransport(timeout=args.timeout)({
            "endpoint": args.endpoint, "model": args.model, "prompt": PROBE_PROMPT,
            "cloud_allowed": args.cloud_allowed})
    except providers.ProviderTransportError as error:
        check("probe completed", False, providers.redact_provider_text(str(error)))
        report["failure_class"] = providers.classify_provider_error(error)
        report["latency_ms"] = int((time.time() - started) * 1000)
        return 4, report
    report["latency_ms"] = int((time.time() - started) * 1000)
    text = reply.get("text", "")
    report["response_bytes"] = len(text.encode("utf-8"))
    report["response_bytes_bounded"] = report["response_bytes"] <= MAX_REPORTED_BYTES
    check("probe completed", True, f"{report['latency_ms']} ms, {report['response_bytes']} bytes")

    try:
        parsed = tools.parse_round_proposal(text)
    except tools.ToolCallError as error:
        check("proposal schema", False, str(error)[:300])
        report["response_preview"] = text[:400]
        return 3, report
    check("proposal schema", True, f"status={parsed['status']}, {len(parsed['operations'])} operation(s)")
    report["proposal"] = {"status": parsed["status"], "operations": len(parsed["operations"])}
    return 0, report


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    code, report = run(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return code
    for entry in report.get("checks", []):
        print(f"[{'ok' if entry['ok'] else 'FAIL'}] {entry['check']}: {entry['detail']}")
    if "models" in report:
        print(f"installed models: {', '.join(report['models']) or '(none)'}")
    if "latency_ms" in report:
        print(f"latency: {report['latency_ms']} ms · response: {report.get('response_bytes', 0)} bytes")
    if code == 0:
        print("Diagnostic passed. This proves the endpoint answers with schema-valid JSON; it does not prove a "
              "coding round works. Use the approval-gated round flow for that.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
