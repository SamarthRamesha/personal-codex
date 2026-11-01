# Project status

Updated: 2026-11-01 (Asia/Kolkata)

## Current milestone: local control-plane vertical slice

Continuity protocol: `NEXT_SESSION_PROMPT.md` is a permanent, ready-to-use cross-account handoff. It is regenerated after each meaningful verified milestone, on user request, and before usage exhaustion; it must embed the recursive continuation protocol for the next account.

GitHub protocol: `origin` is the official `https://github.com/SamarthRamesha/personal-codex.git` remote. Meaningful verified milestones are committed and pushed to `main` when available, without force-pushing or overwriting unexpected history.

GitHub status: the previously empty remote was verified and initial local history was published on 2026-11-01; `origin/main` was confirmed at `2526fb4` after the push.

Implemented and verified:

- Python local service with SQLite persistence (`app/server.py`).
- Browser dashboard for project registration and task-plan creation (`web/`).
- Repository summary that excludes common generated directories and secret-named files.
- Role-based task plan: planner, developer, testing, independent reviewer.
- Approval and model-provider registries; no provider secret values are stored.
- Approval-gated Git worktree creation and exact-command execution API, constrained to task-owned workspaces and an explicit development command allowlist.
- Dashboard task detail, approval decision controls, workspace requests, command-approval requests, execution controls, and event/output inspection.
- Approval decisions are one-way: a pending request may be approved or rejected once, but never altered afterward.
- Unit tests for secret exclusion, path validation, repository detection, and planning.
- An opt-in HTTP integration test that runs the complete project → task → denied workspace → approved workspace → denied command → approved command lifecycle using disposable Git and SQLite data.
- Recoverable clean-workspace release: a critical approval is required, dirty worktrees are refused, the worktree is removed, and its Git branch remains as a recovery checkpoint.
- User-approved recovery-branch merge and deletion: merges are previewed without changing the repository, conflict previews are reported, and merge/deletion each require a separate critical approval.
- Merge approvals bind the reviewed source and target commit IDs; if either branch changes, the approval cannot be reused.
- Provider registration now validates adapter metadata without connecting: it supports Ollama and OpenAI-compatible endpoint descriptors, requires loopback endpoints unless cloud consent is explicitly `true`, and accepts only environment-variable names as secret references.
- Provider adapter foundation: injected deterministic transports accept only an explicit request object, never receive `secret_ref`, and support commit-bound request digests without network I/O.
- Resource-aware execution: 1–300 second wall timeout; child CPU, file-size, descriptor, address-space limits where supported; 50 MiB child-file cap; 200 kB retained redacted output cap.

Verification completed:

- `python3 -m unittest discover -s tests -v` — 8 unit tests passed; the listener integration test is correctly skipped unless explicitly enabled.
- `PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v` — all 9 tests passed, including conflict reporting, stale-approval rejection, merge, and recovery-branch deletion.
- After provider-boundary coverage, the default suite passed 10 unit tests and the opt-in HTTP suite passed all 11 tests.
- After the injected provider transport foundation, the default suite passed 11 unit tests; the listener integration test remains opt-in.
- `python3 -m py_compile app/server.py` — passed.
- HTTP smoke test completed after using an approved unsandboxed loopback test: `/api/health` returned `{"ok": true, "version": "0.1.0", "mode": "local-control-plane"}` and the dashboard served successfully. The process was stopped after the check.
- The post-UI-update loopback smoke test again confirmed the health endpoint, task-workspace dashboard markup, and the updated JavaScript asset; process stopped after the check.

Not implemented: provider invocation/streaming/tool calls, native desktop shell, real multi-agent executor, server connector, indexer/LSP, encrypted secrets, TLS/authenticated remote protocol, UI automation tests, and conflict-resolution tooling.
