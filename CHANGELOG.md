# Changelog

## Mission 1 native client and private API — 2026-11-07

- Added native Tauri 2 / React / TypeScript client (client/API version 0.2.0), original icon, bounded authenticated Rust transport, persisted streaming chat, local-model discovery/selection, project files, task/proposal/diff/approval controls, approved commands and diagnostics.
- Added owner token and expiring cookie sessions, private authenticated TLS startup policy, browser request defenses, body bounds and redacted method/status logs.
- Removed chat's self-approved cloud transmission; cloud chat is disabled. External gateway now requires explicit environment opt-in and network approval. Native-tool support is no longer claimed without implementation.
- Fixed newest-history truncation, atomic text/cursor persistence, duplicate chat turns, stale/unmatched diff presentation, competing approval decisions, lost execution-claim rollback and late planning responses after cancellation. Provider round streaming now defaults on.
- Added pruned bounded context traversal, contained read-only project APIs, configurable own-data storage diagnostics, verified SQLite snapshots and restore into new files only. No automatic deletion or model downloads.
- Verified a genuine installed Qwen 14B coding workflow and the actual native Mac UI. Tests: 177 Python discovered (4 skips with HTTP; 34 default), 2 Vitest tests, 1 Rust test, syntax/type/build checks.
- Confirmed JARVIS identity through existing Tailscale status; read-only SSH authentication failed. No server changes or family-backup access. Mission 1 remains PARTIAL pending live server acceptance.

## 0.5.0 — 2026-11-02

- Cancellation now reaches the running subprocess: the executor polls every 200 ms, sends SIGTERM to the process group, then SIGKILL after a 1.5 s grace period, preserves partial output, and reports exit code 130. A cancelled test command is recorded as `cancelled` rather than a failed test, and later operations do not start.
- Added `GET /api/tasks/{id}/events/stream`: Server-Sent Events over persisted events with SQLite rowid ids, `Last-Event-ID`/`?after=` resumption, a 500-event/120 s bound, keep-alive comments, and clean close on a dead client.
- Added `GET /api/tasks/{id}/agent/diff`: per-file unified diffs for the pending proposal with the bound digest, current digest, occurrence count, stale detection, and a truncated-display flag. The dashboard disables execution when the proposal is stale or its digest no longer matches.
- Added `GET /api/projects/{id}/search`: bounded local repository search that respects `.gitignore` and never returns secret-named files, symlinks or generated directories.
- Added security headers to every response, including a Content-Security-Policy with no inline script/style for the dashboard and `default-src 'none'` for JSON.
- Dashboard: diff review panel, repository search, and a live activity stream with reconnection status.
- Added `tests/test_interaction.py` (15 tests) covering subprocess termination, timeout distinction, diff/hash/stale semantics, search containment and validation, stream resumption and HTTP headers; updated the cancellation round test for the stronger guarantee. Total: 126 tests.

## 0.4.0 — 2026-11-01

- Added evidence-backed memory promotion: proposals require a passing round, carry provenance (task, round, test command, exit code, changed files), are deduplicated, credential-checked, and stored only after explicit approval or rejection.
- Added memory staleness labelling, provenance columns (with an additive migration), and relevance-ranked bounded retrieval against the task and selected context paths.
- Added `OllamaStreamTransport` with bounded NDJSON accumulation, cancellation, redirect/proxy refusal, and rejection of malformed, oversized, erroring or unterminated streams; opt-in via `PERSONAL_CODEX_STREAM_PROVIDER`.
- Added model discovery (`/api/tags`) and `scripts/live_provider_check.py`, a read-only diagnostic with explicit model selection, schema validation, latency and byte reporting, and sanitised errors.
- Added provider health metadata (status, issues, last latency) to `GET /api/providers` and `GET /api/providers/{id}/health`, and recorded latency after each invocation.
- Added secret-shape redaction for provider error bodies.
- Dashboard: project-memory panel with pending proposals and approve/reject, provider status and latency, `.git` excluded from prompt listings and context walks.
- Added OpenAI-compatible SSE streaming with `[DONE]` termination, credential handling and rejection of unterminated or malformed frames.
- Added provider failure classification and a single read-only discovery retry; mutation paths are never retried.
- Added a deterministic, evidence-derived completion summary memory proposal (pending until approved).
- Added 26 tests over the milestone: streaming (both protocols), discovery/retry/classification, redaction, harness behaviour, memory promotion/staleness/retrieval, and UI contracts. Documented measured performance.

## 0.3.0 — 2026-11-01

- Added per-operation cancellation: a persisted cancellation bound to the active round, checked before every tool and test command, revoking the round's approval, preserving completed work, and recording skipped indexes.
- Added an operation-level ledger (status, timing, summary, error, applied flag, before/after hashes) written before and after each operation, with interrupted rows never replayed on restart.
- Enforced test-output and context budgets on the next provider request, refused cancellation of a completed task, and covered test-output exhaustion plus memory injection into the approved prompt.
- Added cumulative per-task budgets for prompt bytes, provider response bytes, test output bytes, context bytes and provider invocations, with clamped environment configuration, refusal before any provider call, a recorded reason, and an explicit confirmed reset.
- Added `app/context.py`: bounded repository manifest, documentation prioritisation, Python/JS symbol outlines, token/failed-test/changed-file ranking, `.gitignore` and secret exclusion, symlink containment, byte caps, a stable context digest, and an untrusted-data prompt block.
- Added `GET /api/tasks/{id}/agent/context` and context/ledger/budget/cancellation data in `GET /agent/rounds` and `GET /agent/report`.
- Added a project-memory foundation with project-scoped CRUD, seven bounded kinds, and credential-pattern rejection.
- Extended the dashboard with cancel task, explicit budget reset, budget meter, operation ledger, and selected-context panels, plus contract tests.
- Added 18 tests: cancellation between operations, ledger persistence and crash recovery, budget refusal/reset, context visibility, context engine relevance/containment/determinism, and memory CRUD.
- Documented the reproducible live Ollama test procedure; live model testing remains pending.

## 0.2.0 — 2026-11-01

- Added a persistent multi-round agent loop: `rounds` table plus `/api/tasks/{id}/agent/round/{request,plan,execute,cancel}`, `GET /agent/rounds`, and `GET /agent/report`.
- Every round requires a fresh provider approval bound to its round number and prompt digest, and a fresh proposal approval bound to the proposal digest, workspace branch/path, and reviewed file hashes.
- Added bounded test feedback: each round records the test command, exit code, redacted output tail, failed test names, changed files, and errors, and the next prompt embeds that evidence.
- Added strict round status validation (`continue`, `complete`, `blocked`, `failed`) and server-verified completion evidence; false completion claims are stored as `rejected-completion` without touching the workspace.
- Added loop safety: round, elapsed-time, and operation limits; single-use rounds; duplicate-response and duplicate-digest refusal; cancellation; and a distinction between a failing test run and a failed tool operation.
- Added restart recovery: rounds left `executing` are marked `interrupted` on startup, their proposals are closed, and the task returns to `needs-another-round`.
- Added dashboard round history with limits, elapsed time, per-round test results, errors, and a final report of changed files, test runs, and diff summary.
- Added five opt-in HTTP tests covering self-correction, evidence-checked completion, per-round approvals, duplicate refusal, the round limit, and cancellation, plus round unit tests, restart-recovery coverage, and dashboard contract checks; the dashboard ignores repeated action clicks while a request is in flight.

## 0.1.0 — 2026-11-01

- Created local-first Personal Codex control-plane foundation.
- Added SQLite persistence, project registration, task plans, approvals, provider metadata, and dashboard.
- Added security-oriented repository filtering and unit coverage.
- Added approval-gated task workspaces and exact command execution boundary.
- Added dashboard controls to inspect and decide approvals, request isolated workspaces, request exact command approval, and inspect task events/output.
- Added disposable, opt-in HTTP integration coverage for the approval-gated workspace and command lifecycle.
- Added resource-limited execution and critical-approval clean-workspace release with retained recovery branches.
- Added read-only merge previews, conflict reporting, critical-approved merges, and separately approved recovery-branch deletion. Approval records bind the reviewed Git commit IDs.
- Added strict provider metadata validation and capability discovery for future Ollama/OpenAI-compatible adapters, without secret access or provider network I/O.
- Added approval-gated provider invocation: bound approvals over task, provider, endpoint, model, prompt digest, and cloud flag; a separate `network` approval for cloud-consented providers; a fail-closed default transport; and a bounded, redacted invocation ledger.
- Added dashboard provider-invocation controls and a provider-response ledger.
- Added browser-free dashboard contract tests for element IDs, button wiring, routed API paths, gated controls, and local-only assets.
- Added real provider transports: Ollama `/api/chat`/`/api/generate` and OpenAI-compatible `/chat/completions`, standard-library only, with redirect refusal, proxy-free requests, timeouts, response caps, sanitised errors, and loopback enforcement.
- OpenAI-compatible credentials are resolved from the named environment variable only at call time and never stored or logged; cloud providers require a secret reference.
- Added a provider adapter test suite against an ephemeral loopback stub server plus a no-override API integration test.
- Added dashboard provider transport-policy hint and duplicate-invocation guard.
- Added `app/tools.py`: strict closed-schema agent tool proposals (`list_files`, `read_file`, `apply_patch`, `run_tests`), workspace containment with symlink-escape refusal, secret exclusion, hash-bound patches, bounded execution with stop-on-failure semantics.
- Added approval-gated agent lifecycle API: `/agent/request` (deterministic prompt approval), `/agent/plan` (validated provider proposal + file hashes), `/agent/execute` (approved digest only, single execution), and `GET /agent` for the latest proposal.
- Added agent proposal and execution-result panels to the dashboard with approval-bound execute control.
- Added `tests/test_tools.py` covering schema rejection, path and symlink escapes, secret paths, patch hash binding, stale-file rejection, runner failure handling, and the full HTTP proposal → approval → execution lifecycle.
- Rewrote `README.md` as a complete project guide covering architecture, providers, the agent workflow, security model, and tests.
