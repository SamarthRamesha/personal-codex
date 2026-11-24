# Freebuff ↔ Codex coordination

Freebuff implementation agent owns this branch. OpenAI Codex is the technical lead, security
reviewer and integration agent. Updated 24 November 2026.

> **Incident, 24 November — `main` was fast-forwarded unintentionally.** A `cloud_git push` without
> an explicit `branch` pushed this checkout's HEAD, which fast-forwarded `origin/main` from
> `64189ef` to `da08db1`. Nothing was rewritten, no force-push was used and no commit was lost: it
> is a plain fast-forward, and it carried the 62 automation-branch commits plus the two checkpoints
> of this branch. It was still a move to `main` without Codex review, which the operating rules
> forbid. It was **not** reverted here, because reverting would need a force-push or a revert commit
> over 62 commits, and both are outside this agent's authority. `main` now contains this branch's
> head, so it must be treated as the integration target Codex reviews, not as a reviewed baseline.
> Every later push from this chat names the branch explicitly. Owner/Codex decision required:
> accept `da08db1` as `main`, or reset `main` to `64189ef` with owner authorization.

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


### 2. Composer consistency and round evidence

- Selecting an installed model now also selects the provider that owns it (`desktop/src/providerChoice.ts`),
  because offline mode seeds one provider row per allowed model and the backend refuses a model the
  chosen provider does not own. The panel no longer offers a model that cannot be sent.
- A coding round's `test_result` is rendered as evidence (`desktop/src/roundEvidence.ts`,
  `RoundEvidence.tsx`): the command and exit code, the failing test lines, the changed files and the
  bounded output. A round that ran no test is shown as **not** passing instead of as raw JSON.
- Tests: `providerChoice.test.ts` (2), `roundEvidence.test.tsx` (4).

### 3. Objective task report in the panel

`TaskReportPanel` shows `/api/tasks/{id}/agent/report` — the backend's report built from recorded
rounds: executed rounds, passing and failing test runs with their commands and exit codes, changed
files, remaining round budget and the diff stat. The panel previously showed only the model's own
summary, so a task's actual evidence was not visible. `desktop/src/taskReport.ts` is pure and
tested; an unreported exit code is shown as unproven, and no state is upgraded to "complete".
Tests: `taskReport.test.ts` (5).

### 4. Message-search hits in the sidebar

`GET /api/conversations/search` had no panel caller, so the sidebar could only say a conversation
matched without showing where. The panel now lists one attributed hit per conversation (speaker,
snippet, title) and opens that conversation on click; `desktop/src/searchHits.ts` is pure and
tested, the list is bounded to eight rows, and a short query is never sent. Tests: 3.

### 5. Context disclosure for a conversation

`GET /api/conversations/{id}/context` reports what the next turn can draw on and which bound
applies, and the composer shows it in a `Context` disclosure: prompt-input messages against the
char bound, excluded turns, included versus stored project memory and attachments, indexed document
count and whether FTS search exists on this backend. It reuses the prompt's own ranked memory
selection, reads no project file, calls no model and states that a count is not a record of what a
model used. `server.conversation_context_report` plus `desktop/src/chatContext.ts`; tests: 4 store,
1 HTTP-gated and 4 frontend.

### 6. Conversation management in the sidebar

The backend already supported pinning, archiving, archived listing and soft delete, with tests, but
the panel offered none of it: an old conversation could not be pinned, hidden or removed from the
client. The selected conversation now has pin, archive/restore and a two-click delete, and the
conversation list can switch between active and archived.

Requests are built by `desktop/src/conversationActions.ts` (pure, 4 tests), so the route, method and
body are testable; deleting the open conversation clears the view instead of leaving a dead id.

Known limit: sending from a conversation opened through the archived view refreshes the sidebar to
the active list (the conversation stays open). The list refresh used after each action is separate
from the send path, which was left alone to avoid restarting streams.

## Verification actually run (all on this Linux workspace)

| Check | Result |
|---|---|
| `PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests` | 445 discovered, 441 passed, 4 skipped, 72.3 s |
| `tests.test_environment` alone | 16 passed |
| `npm test` in `desktop` | 71 passed (16 files) |
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
