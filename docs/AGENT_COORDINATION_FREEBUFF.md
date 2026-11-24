# Freebuff ↔ Codex coordination

Freebuff implementation agent owns this branch. OpenAI Codex is the technical lead, security
reviewer and integration agent. Updated 24 November 2026.

## Branch and base

| Item | Value |
|---|---|
| Branch | `personal-codex/freebuff-implementation` (published, upstream set to `origin`) |
| Base | `d15def9` — tip of `personal-codex/mac-automation` |
| Published main | `origin/main` = `origin/personal-codex/stabilization` = `64189ef` (an ancestor of the base) |
| Checkpoints | see `git log --oneline origin/main..personal-codex/freebuff-implementation` |

Codex's branch `personal-codex/codex-integration` was not created, read or modified here, and no
other agent's worktree was touched. Nothing was merged into `main`, no history was rewritten and
no force-push was used.

## State recovered from the interrupted session

- **Unpublished commits, preserved:** `personal-codex/mac-automation` had two commits beyond its
  published tip (`f6224e2`): `1a778ff` (docs/API.md, autonomous report wording) and `d15def9`
  (tests/test_conversations.py, one-answer guards). They are contained in this branch's base and
  were not rewritten.
- **Dangling auto-stash still readable:** `542fd7d` (23 Nov 07:51, app/conversations.py +11/−1).
  `git stash list` is empty; it is reachable by hash only. Not applied — recorded so it is not
  lost. Codex should decide whether it is still wanted.
- **CI YAML correction kept:** `37de1f1` (quoted `--only-binary=:all:`) is present. The workflow
  parses with `yaml.safe_load` and still lists the backend, frontend and native jobs.
- No stash entries and no uncommitted files were left in the working tree.
- The interrupted chat's directory is not readable from this chat and its worktree is marked
  prunable; nothing was attempted against it.

## Completed in this branch

### 1. Project environment readiness (read-only)

`GET /api/projects/{id}/environment` reports detected manifests (node, python, rust, go),
dependency state **with its evidence**, the exact single install commands, and the project's
declared `dev`/`serve`/`start`/`preview` scripts with a port only when the script declares one.

- New `app/environment.py`; route in `app/server.py`; panel section `desktop/src/ProjectReadiness.tsx`
  with pure display helpers in `desktop/src/readiness.ts`.
- Installs, starts and downloads nothing; reads no lockfile, source file or `.env`; does not follow
  a symlinked manifest; reports Rust/Go state as `unknown` rather than guessing.
- Docs: `docs/PROJECT_ENVIRONMENT.md`, `docs/API.md`, `docs/README.md`, `docs/IMPLEMENTATION_MATRIX.md`.
- Tests: `tests/test_environment.py` (16: 14 unit, 2 HTTP-gated), `desktop/src/readiness.test.ts` (4).

## Verification actually run (all on this Linux workspace)

| Check | Result |
|---|---|
| `PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests` | 440 discovered, 436 passed, 4 skipped, 70.7 s |
| `tests.test_environment` alone | 16 passed |
| `npm test` in `desktop` | 49 passed (10 files) |
| `npm run build` in `desktop` | `tsc -b` + Vite build passed |
| `yaml.safe_load(.github/workflows/verify.yml)` | three jobs, all steps present |
| Rust/native | not run in this environment (no macOS toolchain here) |

Hosted CI is read from the run page and job pages only; this workspace cannot read job logs. A red
run without a job list is a workflow-load failure, not a test failure.

## Coordination decisions for Codex

1. **CI trigger extended** to `personal-codex/freebuff-implementation` so this branch gets hosted
   verification. It is additive; `main`, `stabilization` and `mac-automation` triggers are
   unchanged. YAML is parsed before pushing (the R-35 lesson).
2. **No new authority.** The readiness report is read-only and returns `executed: false` /
   `network: false`; it cannot install, run, or read secrets. It is not an executor.
3. **The base is `mac-automation`, not `main`.** `main` is 62 commits behind the automation branch
   and does not contain the CI correction, so branching from `main` would have silently dropped
   work. Integration into `main` should therefore fast-forward through this branch, not around it.

## Not verified here

- No macOS native run, no permissioned UI session, no real Ollama model, no JARVIS access.
- The panel was type-checked, unit-tested and built; it was not opened, so its rendered layout is
  unverified.
- Nothing in this branch closes R-01, R-05, R-06, R-13 or any JARVIS/deployment gate.

## Safety constraints kept

No force-push, no history rewrite, no merge to `main`, no `personal-codex-diagnostic.txt` access,
no OS permission changes, no TCC or Automation changes, no browser-profile or credential access, no
JARVIS/Docker/family-service changes, and no weakening of approval or execution checks.
