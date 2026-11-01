# Project status

Updated: 2026-11-01 (Asia/Kolkata)

## Current milestone: approval-gated provider invocation

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
- Provider invocation is now an end-to-end approval-gated flow: `POST /api/tasks/{id}/provider-request` records a pending approval bound to task, provider, endpoint, model, prompt SHA-256, and cloud flag; `POST /api/tasks/{id}/invoke` requires that exact approved binding. Loopback providers need `provider-invoke`; cloud-consented providers need a separate `network` approval.
- The adapter receives only kind, endpoint, model, and prompt — never the secret reference. The shipped transport (`unavailable_provider_transport`) fails closed, so no prompt leaves the machine. Responses are bounded, redacted, persisted with the prompt digest, and listed at `GET /api/tasks/{id}/invocations`.
- Dashboard wiring for provider invocation: provider select, approval request, invoke action, and a provider-response ledger.
- Browser-free dashboard contract tests (`tests/test_ui.py`) assert that scripted element IDs exist, every button is wired, every `/api/...` path used by the script is routed, gated actions are all present, and only local assets are loaded without browser-stored secrets.
- Resource-aware execution: 1–300 second wall timeout; child CPU, file-size, descriptor, address-space limits where supported; 50 MiB child-file cap; 200 kB retained redacted output cap.

Verification completed (2026-11-01, this session):

- `python3 -m unittest discover -s tests -v` — 19 unit tests passed; the listener integration test is correctly skipped unless explicitly enabled.
- `PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v` — all 20 tests passed, including the provider invocation lifecycle (denied → approved → invoked → changed prompt rejected → ledger) and the cloud `network`-approval separation.
- `python3 -m py_compile app/server.py` — passed.
- `node --check web/app.js` — passed.
- Loopback smoke test with the real server: `/api/health` OK; dashboard markup and script expose the provider controls; invoke before approval returned 403; the approval detail bound endpoint/model/prompt digest; invoking with that approval but the default transport returned the fail-closed error and wrote no ledger row; a cloud endpoint without consent was rejected. The server was stopped after the check.

Environment note: this cloud workspace ran Python 3.12.3 and Node 26.13.0; the owner's Mac has Python 3.13.9 and Node 24.22.1.

Not implemented: real provider network adapters (Ollama/OpenAI transport), streaming and tool calls, a real multi-agent executor, native desktop shell, server connector, indexer/LSP, encrypted secrets, auth/TLS remote protocol, conflict-resolution tooling, and browser-automation UI tests.
