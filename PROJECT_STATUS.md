# Project status

Updated: 2026-11-01 (Asia/Kolkata)

## Current milestone: real approval-gated provider transports

Continuity protocol: `NEXT_SESSION_PROMPT.md` is a permanent, ready-to-use cross-account handoff. It is regenerated after each meaningful verified milestone, on user request, and before usage exhaustion; it must embed the recursive continuation protocol for the next account.

GitHub protocol: `origin` is the official `https://github.com/SamarthRamesha/personal-codex.git` remote. Meaningful verified milestones are committed and pushed to `main` when available, without force-pushing or overwriting unexpected history.

Implemented and verified:

- Python local service with SQLite persistence (`app/server.py`).
- Browser dashboard for project registration and task-plan creation (`web/`).
- Repository summary that excludes common generated directories and secret-named files.
- Role-based task plan: planner, developer, testing, independent reviewer.
- Approval and model-provider registries; no provider secret values are stored.
- Approval-gated Git worktree creation and exact-command execution API, constrained to task-owned workspaces and an explicit development command allowlist.
- Dashboard task detail, approval decision controls, workspace requests, command-approval requests, execution controls, and event/output inspection.
- Approval decisions are one-way: a pending request may be approved or rejected once, but never altered afterward.
- Recoverable clean-workspace release, read-only merge preview with conflict reporting, critical-approved merge, and separately critical-approved recovery-branch deletion. Merge approvals bind the reviewed source and target commit IDs; deletion approvals bind the recovery-branch commit ID.
- Provider registration validates `ollama` and `openai-compatible` metadata only: absolute HTTP(S) endpoints without embedded credentials, loopback required unless `cloud_allowed: true`, and `secret_ref` restricted to environment-variable names. Registration and capability discovery never read a secret or contact a provider.
- Provider invocation is an end-to-end approval-gated flow: `POST /api/tasks/{id}/provider-request` records a pending approval bound to task, provider, endpoint, model, prompt SHA-256, and cloud flag; `POST /api/tasks/{id}/invoke` requires that exact approved binding. Loopback providers need `provider-invoke`; cloud-consented providers need a separate `network` approval. Responses are bounded, redacted, persisted with the prompt digest, and listed at `GET /api/tasks/{id}/invocations`.
- Real provider transports (`app/providers.py`, standard library only): Ollama `/api/chat` (with `/api/generate` support) and OpenAI-compatible `/chat/completions`. Shared hardening: `http.client` with no proxy-env or redirect handling (3xx refused), connection timeout (60 s default), 1 MB response cap, JSON shape validation, sanitised error text, and an independent loopback check unless the provider is cloud-consented.
- OpenAI-compatible credentials are resolved from the named environment variable inside the transport at call time, placed only in the `Authorization` header, and never stored or logged. A cloud provider without a secret reference is refused, and a missing credential fails before any request.
- `server.PROVIDER_TRANSPORT` remains the injection seam: `None` selects the built-in adapters, a callable overrides them, and `unavailable_provider_transport` restores a hard fail-closed service.
- Dashboard wiring for provider invocation: provider select with a transport-policy hint, approval request, invoke action with duplicate-submission guard, and a provider-response ledger.
- Browser-free dashboard contract tests (`tests/test_ui.py`) assert that scripted element IDs exist, every button is wired, every `/api/...` path used by the script is routed, gated actions are all present, and only local assets are loaded without browser-stored secrets.
- Provider adapter tests (`tests/test_providers.py`) run against an ephemeral loopback stub server: request shape and path, response extraction, malformed JSON, HTTP errors, redirect refusal, connection refusal, timeout, oversized response, unexpected structure, invalid endpoints, non-loopback refusal, credential handling, and transport selection. No external network or real model is used.
- Resource-aware execution: 1–300 second wall timeout; child CPU, file-size, descriptor, address-space limits where supported; 50 MiB child-file cap; 200 kB retained redacted output cap.

Verification completed (2026-11-01, this session):

- `python3 -m unittest discover -s tests -v` — 40 tests, `OK (skipped=2)`: the two listener-gated tests are correctly skipped unless explicitly enabled.
- `PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v` — all 40 tests passed, including the provider invocation lifecycle and a no-override API test that reaches the built-in Ollama adapter through a stub model server.
- `python3 -m py_compile app/server.py app/providers.py` — passed.
- `node --check web/app.js` — passed.
- Earlier loopback smoke test confirmed health, dashboard provider controls, 403 before approval, bound approval detail, and rejection of a cloud endpoint without consent; later transport coverage replaced the fail-closed-only check with the stub-server adapter suite above.

Environment note: this cloud workspace ran Python 3.12.3 and Node 26.13.0; the owner's Mac has Python 3.13.9 and Node 24.22.1.

Not implemented: provider streaming and tool calls, a real multi-agent executor, native desktop shell, server connector, indexer/LSP, encrypted secrets, auth/TLS remote protocol, conflict-resolution tooling, and browser-automation UI tests. No live model has been exercised: all adapter tests use a local stub server.
