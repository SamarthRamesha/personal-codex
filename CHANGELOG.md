# Changelog

## 0.3.0 — 2026-11-01

- Added per-operation cancellation: a persisted cancellation bound to the active round, checked before every tool and test command, revoking the round's approval, preserving completed work, and recording skipped indexes.
- Added an operation-level ledger (status, timing, summary, error, applied flag, before/after hashes) written before and after each operation, with interrupted rows never replayed on restart.
- Added cumulative per-task budgets for prompt bytes, provider response bytes, test output bytes, context bytes and provider invocations, with clamped environment configuration, refusal before any provider call, a recorded reason, and an explicit confirmed reset.
- Added `app/context.py`: bounded repository manifest, documentation prioritisation, Python/JS symbol outlines, token/failed-test/changed-file ranking, `.gitignore` and secret exclusion, symlink containment, byte caps, a stable context digest, and an untrusted-data prompt block.
- Added `GET /api/tasks/{id}/agent/context` and context/ledger/budget/cancellation data in `GET /agent/rounds` and `GET /agent/report`.
- Added a project-memory foundation with project-scoped CRUD, seven bounded kinds, and credential-pattern rejection.
- Extended the dashboard with cancel task, explicit budget reset, budget meter, operation ledger, and selected-context panels, plus contract tests.
- Added 16 tests: cancellation between operations, ledger persistence and crash recovery, budget refusal/reset, context visibility, context engine relevance/containment/determinism, and memory CRUD.
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
