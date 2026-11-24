# Personal Codex: continuation prompt

Updated 24 November 2026 (end of the second Freebuff sprint). Continue on
**`personal-codex/freebuff-implementation`**, published at **`a79bdee`** plus the commit that carries
this document. Verify with `git log --oneline -6`, `git status --porcelain` and `git ls-remote origin`.

## Do not do these

- **Do not push, merge, reset or revert `main`.** It is at `da08db1` because of an unintended
  fast-forward (risk R-36) that is still awaiting the owner's decision. Publishing any of it needs
  owner authorization.
- Do not touch `personal-codex/codex-integration` (Codex's branch), `personal-codex/mac-automation`,
  or create another development branch.
- Always pass the branch explicitly to `cloud_git push`; an omitted branch defaults to `main` and is
  what caused R-36.
- Never read, stage, modify or archive `personal-codex-diagnostic.txt`. Preserve `web/style.css`,
  `web/chat.js`, `.recovery-backup/`, `.safety/`, `diagnostics/`, `SESSION_HANDOFF.md`, application
  bundles, profiles, local model caches and Git history. No force-push, no hard reset, no TCC or OS
  permission changes, no weakening of approvals.
- **JARVIS is offline and completely out of scope.** Do not probe it, its SSH, Tailscale, ports,
  Docker, networking, storage or backups, and do not attempt any deployment or recovery.

## Environment reality

This workspace is Linux with no macOS toolchain, no browser and no Ollama model. Rust/native checks,
windowed UI acceptance and live-model behaviour **cannot** be run or claimed here. The hosted macOS
`native` job compiles the helper and runs its Rust tests: that is compile plus policy evidence, not
GUI acceptance.

## What this branch contains

Read `docs/AGENT_COORDINATION_FREEBUFF.md` for the full record. In order:

1. Project environment readiness, read-only (`GET /api/projects/{id}/environment`, readiness panel).
2. Provider/model consistency in the composer and round evidence.
3. Objective task report panel (`GET /api/tasks/{id}/agent/report`).
4. Message-search hits in the sidebar.
5. Conversation context disclosure (`GET /api/conversations/{id}/context`).
6. Conversation pin / rename / archive / two-click delete, archived view and project filter.
7. Native CI casing fix: four helper modules renamed, plus `tests/test_frontend_filenames.py`.
8. Per-project task list with real statuses and `GET /api/tasks?project_id=…`.
9. Readiness now reports declared check commands and `PATH`-looked-up toolchain state (starts nothing).
10. Task-needs-owner notice and timestamped, bounded Activity trail.
11. Delivered tasks can no longer be cancelled into `cancelled` (409), and Cancel is hidden then.
12. Arrow-key navigation of the visible conversation list from the search box.

## Verification actually run here

- Backend: `PERSONAL_CODEX_HTTP_TESTS=1 PERSONAL_CODEX_DATA=/tmp/<dir> python3 -m unittest discover -s tests`
  → **454 tests, OK (4 skipped)**.
- `python3 -m unittest tests.test_server` → 21 OK; `tests.test_environment` → 21 tests (2 HTTP-tier skipped).
- Frontend: `npm test` → **95 passed (18 files)**; `npm run build` (tsc -b + Vite) → passed.

## Hosted CI

Runs #107–#110 were cancelled by the workflow's `cancel-in-progress` group when the next checkpoint was
pushed; they are not failures. **Run #111 (`a79bdee`) completed successfully in 4 m 3 s**, so backend,
frontend and the macOS `native` job passed on the whole sprint. Runs for later commits must be read
on their own run page (the GitHub REST API is rate-limited from this host; job logs need
authentication, so job status badges and run conclusions are what is readable).

## Outstanding

- **Mac GUI acceptance**: no panel was ever opened here. The task list, readiness additions, notice,
  Activity timestamps and keyboard navigation are unit-tested, not visually accepted.
- The task list is bounded at 20 rows per project and does not page into older history.
- An interrupted round still cannot resume; it requires a fresh proposal (documented, not automated).
- `scripts/full_task_acceptance.py` exits 1 on Linux by design ("requires the verified macOS process
  sandbox"). That is a platform gate, never a pass.
- `main` (R-36) is unresolved and owned by the owner/Codex.

## Next highest-value work

1. Paging or a filter for older tasks in the project task list.
2. A reviewed dependency-install / dev-server action proposal built on the existing approval machinery
   (do not install or start anything automatically).
3. Round-level resume messaging and, if the backend supports it, an explicit resume path.
4. Codex review of the twelve checkpoints above before anything is proposed for integration.
