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

### 7. Native CI casing failure and its fix

The hosted native job failed at "Prepare embedded frontend": `tsc -b` reported TS1261/TS1149
("file name differs from already included file name only in casing") and then missing exports. The
cause was mine, from checkpoints 2–6: four pairs of files whose names differed only in case —
`RoundEvidence.tsx`/`roundEvidence.ts`, `TaskReport.tsx`/`taskReport.ts`,
`ChatContext.tsx`/`chatContext.ts`, `ConversationActions.tsx`/`conversationActions.ts`. A
case-insensitive checkout cannot hold both, so the helper module and its importer disagree on the
Mac runner.

Fix: the four helper modules and their tests were renamed to unambiguous names, with the components
unchanged — `roundEvidenceSummary.ts`, `taskReportSummary.ts`, `chatContextSummary.ts`,
`conversationActionRequests.ts`. Imports were updated; the Linux build stayed green at every step,
which is exactly why the Linux-only checks had not caught it.

Regression check: `tests/test_frontend_filenames.py` (3 tests, in the backend job) fails when two
files in `desktop/src` or `desktop/src-tauri` have stems that differ only in case (the same stem with
different extensions, such as `icon.png`/`icon.icns`, is allowed), and when a relative import does not
resolve to exactly one real file. A deliberately re-created collision (`SearchHits.ts` beside
`searchHits.ts`) was used as a negative control: the check failed, and passed again once removed.

## Verification actually run (all on this Linux workspace)

| Check | Result |
|---|---|
| `PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests` | 448 discovered, 444 passed, 4 skipped, 72.3 s |
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

## Handoff — end of the 24 November Freebuff allocation

### 1. Branch and commit

- Branch `personal-codex/freebuff-implementation`, published at **`cfeaa61`** (upstream `origin`).
- Base `d15def9` (tip of `personal-codex/mac-automation`). `main` is **`da08db1`** because of the
  unintended fast-forward in R-36: it contains this branch up to `da08db1` but none of the later
  checkpoints.
- `personal-codex/codex-integration` exists on the remote (`bbf5385`) and was never read, checked
  out or modified here.

### 2. Published and unpublished changes

- Published: every checkpoint up to `cfeaa61` on the feature branch; up to `da08db1` on `main`.
- Unpublished on this branch: nothing; the working tree is clean.
- Still outside the branch: `origin/personal-codex/mac-automation` remains at `f6224e2` even though
  `1a778ff` and `d15def9` are contained in this branch, and the dangling stash `542fd7d` is still
  reachable only by hash.

### 3. Implemented in this allocation (six checkpoints)

1. Read-only project environment readiness (`GET /api/projects/{id}/environment`, panel section).
2. Model selection selects the owning provider; round evidence replaces a raw JSON dump.
3. Objective task report in the workspace (`GET /api/tasks/{id}/agent/report`).
4. Attributed message-search hits in the sidebar (`GET /api/conversations/search`).
5. Context disclosure for a conversation (`GET /api/conversations/{id}/context`).
6. Pin / archive-restore / two-click soft delete and an archived view for conversations.

New tests: 16 (`test_environment.py`), 4 store + 1 HTTP (`test_conversations.py`), 26 frontend tests
across seven new test files.

### 4. Verification actually run here

| Command | Result |
|---|---|
| `PERSONAL_CODEX_HTTP_TESTS=1 PERSONAL_CODEX_DATA=/tmp/pcfinal python3 -m unittest discover -s tests` | **448 discovered, 444 passed, 4 skipped**, 71.2 s |
| `npm test` (desktop) | **71 passed**, 16 files |
| `npm run build` (desktop) | `tsc -b` + Vite build passed |
| `yaml.safe_load(.github/workflows/verify.yml)` | three jobs, all steps present |

Not run: Rust/native (no macOS toolchain), real Ollama model, any JARVIS access, and the macOS-gated
acceptance scripts — `scripts/full_task_acceptance.py` stops with `The autonomous runner requires the
verified macOS process sandbox`, which is a platform gate, not a passing check.

### 5. CI outcomes

**Not read.** The unauthenticated GitHub API was rate-limited from this host (HTTP 403) all session,
and job logs need authentication. The workflow was extended to trigger on this branch at `da08db1`,
so runs may exist for `da08db1`, `ca75925`, `1db2835`, `a1eaba0` and `cfeaa61`; Codex or the owner
must read the run and job pages. No hosted-CI claim is made here, and a red run with no job list is a
workflow-load failure, not a test failure (R-35).

### 6. Unfinished work

- The panel was type-checked, unit-tested and built but **never opened**, so layout and placement of
  every new section are unverified.
- No rename control yet, despite `PATCH /api/conversations/{id}` supporting `title`; no per-project
  chat filter; sending from an archived conversation returns the sidebar to the active list.
- Dependency installation and dev-server processes remain operator actions; the readiness report is
  diagnostic only.
- macOS native acceptance (R-01, R-05, R-06, R-13) and every JARVIS/deployment gate are untouched.

### 7. Integration requirements for Codex

- Review the six checkpoints in order; each is additive and independent, and none adds authority,
  schema migration or execution path. The only non-read-only additions are the conversation controls,
  which call routes the backend already had and already tests.
- Conflict hotspots if you also edited them: `desktop/src/App.tsx` (conversation list markup) and
  `app/server.py` (module imports and the `GET /api/conversations/` branch).
- Decide R-36 first: accept `da08db1` as `main`, or reset `main` with owner authorization.

### 8. Risks

R-36 is the only new one and is open until the owner decides. R-01–R-35 are unchanged by this work.

### 9. Next highest-value work

1. Read the hosted CI for `cfeaa61` and fix anything it reports (native job included).
2. Open the panel on a real Mac and verify the six new sections render and behave.
3. Add a rename control and a per-project chat filter; keep the archived-list refresh coherent.
4. Then the listed coding gaps: dependency installation and dev-server lifecycle as explicit,
   approved actions rather than a report.

### 10. Copyable continuation prompt

```text
Continue Personal Codex as the Freebuff implementation agent on branch
personal-codex/freebuff-implementation (last checkpoint cfeaa61, base d15def9). Read
docs/AGENT_COORDINATION_FREEBUFF.md first, including the R-36 incident: main was fast-forwarded to
da08db1 unintentionally and needs an owner decision. Do not merge to main, rewrite history or
force-push, and always pass an explicit branch to cloud_git push.

State: backend 445 discovered / 441 passed / 4 skipped, frontend 71 passed plus TypeScript/Vite.
Six checkpoints landed: project environment readiness, provider/model consistency with round evidence,
objective task report, message-search hits, conversation context disclosure, and conversation
pin/archive/delete. Nothing was opened in a real panel, and hosted CI was never read.

Next: read hosted CI for cfeaa61 and fix what it reports, then implement a conversation rename
control and per-project chat filtering, then the approved dependency-installation/dev-server
lifecycle. Verify with the same commands and refresh docs/AGENT_COORDINATION_FREEBUFF.md before
handing off. Do not claim macOS, native, model or JARVIS acceptance.
```
