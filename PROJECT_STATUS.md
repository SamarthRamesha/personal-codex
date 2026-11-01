# Project status

Updated: 2026-11-01 (Asia/Kolkata)

## Current milestone: live-provider readiness, memory promotion and streaming

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
- Agent tool layer (`app/tools.py`): closed-schema proposals over `list_files`, `read_file`, `apply_patch`, and `run_tests`; unknown tools/arguments, oversized values, absolute paths, `..`, ignored directories, secret-named files, and symlink escapes are rejected; patches must match exactly once and re-verify the reviewed SHA-256; execution stops at the first failure and marks later operations skipped.
- Agent lifecycle API: `POST /agent/request` (deterministic prompt + approval), `POST /agent/plan` (approved invocation → validated proposal → file hashes → proposal approval), `POST /agent/execute` (approved digest only, atomically claimed once, runs inside the task worktree), and `GET /agent` for the latest proposal and results.
- Dashboard agent panel: extra instructions, request/build/execute controls, proposal operations with patch previews, digest and branch binding, and execution results.
- Multi-round engine: `rounds` table plus `/api/tasks/{id}/agent/round/{request,plan,execute,cancel}`, `GET /agent/rounds`, and `GET /agent/report`. Each round binds a fresh provider and proposal approval to its round number; the next prompt embeds bounded, redacted evidence from previous rounds (test command, exit code, output tail, failed test names, changed files, errors). Default limits are 3 rounds (`PERSONAL_CODEX_MAX_ROUNDS`), 30 minutes per task, and 8 operations per round.
- Objective completion: a `complete` status is rejected unless a passing executed round recorded both a zero-exit test command and an approved file change, and the latest executed round passed. False claims are stored as `rejected-completion` without changing the workspace.
- Loop safety: duplicate provider responses and already-reviewed proposal digests are refused, a round can execute at most once, cancellation invalidates its pending proposal, and a failing test run is distinguished from a failed tool operation.
- Crash recovery: on start, any round still marked `executing` becomes `interrupted` with an event and its proposal is closed, so a restart cannot leave a task stuck or a half-applied round looking passed.
- Dashboard rounds panel: round count/limits/elapsed, per-round status with test exit codes and failed test names, errors, and a final report with changed files and bounded diff stat. Action buttons ignore repeated clicks while a request is in flight.
- Cancellation: `POST /api/tasks/{id}/cancel` persists a cancellation bound to the active round, revokes its approved proposal, and is consulted before every tool operation. Completed operations are preserved, skipped ones are marked `cancelled`, and a cancelled round cannot execute with its old approval.
- Operation ledger (`operations` table): task, round, index, tool, proposal digest, status, timing, summary, error, applied flag, and before/after file hashes, written before and after each operation. Startup marks running rows `interrupted` and never replays them.
- Cumulative budgets (`usage` table): prompt bytes, response bytes, test output bytes, context bytes and invocations, with seven clamped environment variables. Exhaustion refuses the next provider call, records the reason, sets `budget-exhausted`, and requires an explicit confirmed reset.
- Repository context engine (`app/context.py`): manifest, doc/manifest prioritisation, Python `ast` and JS symbol outlines, token/failed-test/changed-file ranking, `.gitignore` and secret exclusion, symlink containment, per-file and total byte caps, stable digest, and an explicitly untrusted prompt block.
- Project memory foundation (`memory` table): seven kinds, bounded content, credential-pattern rejection, project-scoped CRUD, and a "possibly stale" prompt section.
- Dashboard: cancel task, explicit budget reset, budget meter, operation ledger, and selected-context panel with reasons, line ranges and digest.
- Memory promotion: proposals only after a passing round, with provenance, duplicate and credential refusal, explicit approve/reject, staleness labelling and relevance-ranked bounded retrieval.
- Streaming: bounded, cancellable NDJSON (Ollama) and SSE (OpenAI-compatible) adapters with rejection of malformed, unterminated, oversized and erroring streams; opt-in via `PERSONAL_CODEX_STREAM_PROVIDER`.
- Diagnostics: `scripts/live_provider_check.py` (model discovery, explicit model choice, schema probe, latency/bytes, sanitised errors) and provider health/latency metadata in the API.
- Secret-shape redaction for provider error bodies.
- Browser-free dashboard contract tests (`tests/test_ui.py`) assert that scripted element IDs exist, every button is wired, every `/api/...` path used by the script is routed, gated actions are all present, and only local assets are loaded without browser-stored secrets.
- Provider adapter tests (`tests/test_providers.py`) run against an ephemeral loopback stub server: request shape and path, response extraction, malformed JSON, HTTP errors, redirect refusal, connection refusal, timeout, oversized response, unexpected structure, invalid endpoints, non-loopback refusal, credential handling, and transport selection. No external network or real model is used.
- Agent tests (`tests/test_tools.py`): schema and argument validation, path/symlink/secret containment, patch hash binding, duplicate-match refusal, stop-on-failure execution, runner failure handling, digest binding, and an opt-in HTTP lifecycle where an approved proposal edits the worktree, runs a test command, refuses a second execution, and rejects a stale file with the file preserved.
- Resource-aware execution: 1–300 second wall timeout; child CPU, file-size, descriptor, address-space limits where supported; 50 MiB child-file cap; 200 kB retained redacted output cap.

Verification completed (2026-11-01, this session):

- `python3 -m unittest discover -s tests -v` — 84 tests, `OK (skipped=14)`: the listener-gated tests are correctly skipped unless explicitly enabled.
- `PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v` — all 110 tests passed, including the two-round self-correction cycle, evidence-checked completion, per-round approvals, false-completion rejection, duplicate-response refusal, the round limit, cancellation between operations with partial-work preservation, operation-ledger persistence, interrupted-operation recovery, budget refusal and explicit reset, and context visibility.
- `python3 -m py_compile app/server.py app/providers.py app/tools.py app/context.py` — passed.
- `node --check web/app.js` — passed.
- `node --check web/app.js` — passed.
- Earlier loopback smoke test confirmed health, dashboard provider controls, 403 before approval, bound approval detail, and rejection of a cloud endpoint without consent; later transport coverage replaced the fail-closed-only check with the stub-server adapter suite above.

Environment note: this cloud workspace ran Python 3.12.3 and Node 26.13.0; the owner's Mac has Python 3.13.9 and Node 24.22.1.

Not implemented: provider-native tool calling, semantic retrieval, native desktop shell, server connector, encrypted secrets, auth/TLS remote protocol, conflict-resolution tooling, and browser-automation UI tests. No live model has been exercised: all adapter and agent tests use injected transports or a local stub server, so a real Ollama/macOS run remains outstanding.
