# Development log

## 23 November 2026 — the integration seam, an honest 403, and a CI file that never loaded

Continuing the same session. Five commits, one of which was a mistake worth recording in full.

- `bf8f1f0` — the disaster-recovery drill seeded only a conversation title, so a restore that dropped answers, stream chunks, project memory or an approval decision would still have reported success. It now seeds all four, asserts their content survives, asserts post-checkpoint rows do not, and asserts a restored approval is **revoked**. 10 checks pass locally. The same commit installed the recovery wheel in the backend CI job and ran the drill there, because that tier had always been *skipped* in CI — a skip reported as a pass.
- **The mistake.** That install line was `--only-binary=:all: cryptography` with no quotes. It is valid pip, but YAML reads `all:` followed by a space as a mapping key, so the workflow stopped loading. Runs `45140362052`, `45141261480`, `45141954813` and `45142644176` each reported `failure` while starting **no job at all**. Four red runs that said nothing about the code. `37de1f1` quotes the command; the file is parsed with a YAML parser before pushing now, and run `45143352247` is green with the drill step present. The tell was that those run pages had no job list — a failing test always has jobs.
- `555fd32` — `POST /api/conversations/{id}/task` had no test at all, so the chat-to-coding seam (plan, link, approval requirement) was unverified. The new HTTP test asserts the four-step plan, `approval_required`, the stored `conversation_tasks` link, the prompt falling back to the newest user turn, and that creating a task from chat starts **no** run and records **no** execution.
- `4147807` — writing that test exposed a real API wart: `GET /api/tasks/{id}/autonomous` answered **404 "Task not found"** for a task that exists whenever the offline policy was off, the same answer a genuinely missing task gets. The start and stop routes already name the reason with 403. The route now calls the backend and maps `ExecutionDisabledError` to 403, keeping 404 for a task that does not exist.
- `a25753f` — the owner-auth sweep named representative mutations, so the new compact endpoint and the task bridge were outside it. Both now prove 401 without the owner credential.

The 200 path of the autonomous report still needs authenticated offline mode, which that fixture does not run; `test_task_backend` covers `inspect_task` returning `idle` for a task with no run. That split is stated in the test rather than implied.

## 23 November 2026 — retention, project memory and panel increments

Same session, continuing after the native CI repair. Four source commits, each with its own check:

- `3f4e3df` — `start_turn` released nothing when the runtime refused a worker thread: the claim and the `queued` row stayed, so the conversation refused every later turn and one inference slot was held until restart. Fixed and covered by a test that fails on the old code.
- `bae85e0` — streamed deltas are stored twice (a resumable chunk row and the message content), and chunk rows were never reclaimed. `conversations.prune_terminal_chunks` deletes them for terminal answers only, bounded per call, leaving text, conversations and any answer still arriving untouched; `POST /api/maintenance/compact` exposes it.
- `1042c18` — `GET /api/diagnostics` now reports message, chunk, chunk-byte, active and prunable counts so growth is measurable rather than assumed.
- `0c1b6dc` — the settings panel lists those counts and offers the compaction button, disabled when nothing is prunable.
- `eb394a5` — a stopped answer could not be regenerated (only `error` offered Retry), so cancelling an answer left it a dead end. The status-to-action mapping moved into `desktop/src/messageState.ts` with tests; stopped and error regenerate, queued and streaming do not.
- `faffd10` — project chats never saw the project's approved memory even though `memory_lines` already ranked, labelled and byte-bounded it for the coding prompts. Chat context now includes up to six labelled entries with their own 1200-byte budget; a test asserts a credential-shaped row is still refused.

Honest limits of the above: deleting chunk rows does **not** shrink the database file (no VACUUM is run, and the main-database page cap therefore still reflects the historical high-water mark); the panel change was typechecked and built but not viewed; and the memory inclusion is proven at the context-function boundary, not against a live model.

**Verification sweep actually run this session.** Backend `421 tests, OK, 4 skips` with `PERSONAL_CODEX_HTTP_TESTS=1` (69 s); frontend `45 tests / 9 files` and `tsc -b` clean and `vite build` succeeds; the four changed Rust tests pass through the extracted harness. Scripts: `scripts/recovery_drill.py` reported `{"passed": 6, "checkpoint_ms": 14, "restore_ms": 33, "tested_on_jarvis": false}`; `scripts/document_search_acceptance.py` reported `{"success": true, "precision_at_1": 1.0, "mean_reciprocal_rank": 1.0, "model_calls": 0}` with the stale, removed and foreign-project exclusions all true; `scripts/full_task_acceptance.py` stopped at `400 The autonomous runner requires the verified macOS process sandbox`, which is the documented environment block, not a product failure.

**CI, read from the run and job pages.** `999f591` (run `45051415083`) and `93710a8` (run `45054272664`) each failed the native job. `81fd847` (run `45132484092`), `bae85e0` (run `45137737745`) and `eb394a5` (run `45138040157`) each report all three jobs `completed successfully` with no failure marker. Job logs still need authentication from this host, so no log content is claimed.

## 23 November 2026 — native CI failure diagnosed, repaired, verified green

Continuation session; nothing was restarted. The primary checkout stayed on `personal-codex/stabilization` at `12a24d5` with its user modification (`web/style.css`, sha256 `4746cdd0…` unchanged) and its preserved untracked files; feature work stayed in `.worktrees/mac` on `personal-codex/mac-automation`.

**What the failing native job actually ran.** Job metadata for run `45054279088` (commit `93710a8`) reads: `backend` completed **success**, `frontend` completed **success**, `native` completed **failure** at step 6, `Native policy and one-use action tests` (`cargo test --locked`). Step 5, `Build and test Mac automation helper`, was **success**. Job logs still need authentication from this host (the logs endpoint answers 403), so the two failing test names and their `Automation timed out. Scope was invalidated; inspect the target before retrying.` message are taken from the failure report, not re-read here. Later checks of the branch's run pages found the runs an earlier session had called missing: `999f591` → run `45051415083` (backend and frontend success, **native failed**) and `93710a8` → run `45054272664` (same shape). The "no run exists for this commit" claim in the 22 November entry was a stale run-list cache, not an absent run.

**Root cause.** The two failing tests were the only ones whose fixture child had to *answer*; both spawned a hard-coded `/usr/bin/python3` (`b60052f` introduced it) and gave it a 2-second frame deadline. On macOS `/usr/bin/python3` is a Command Line Tools stub, while step 5 of the same job starts `python3` from `PATH` and passed: the fixture therefore depended on an absolute interpreter path the image does not guarantee. When the stub does not answer, `frame()` reaches its deadline and reports the *production* watchdog wording, so a fixture problem read as a lost action and a broken watchdog. The two fixtures that only had to stay silent (`watchdog_bounds_a_silent_child…`, `blocked_input_has_a_real_deadline`) passed for the wrong reason.

**Repair (`81fd847`).** All four fixtures now use `/bin/sh`, which every supported host provides, so no native test depends on an interpreter the image may lack. The fragment case seeds the buffer with the first half of a frame instead of sleeping between writes, which makes the split deterministic instead of timing-dependent, and the response test now asserts the activity event was really recorded so the payload check cannot pass vacuously. Production timeouts, cancellation, response-id binding and scope invalidation are unchanged.

**Verification.** (a) On this Linux host, `write_request`, `frame`, `exchange`, `Transport`, `Broker` and the four tests were extracted verbatim into a standalone crate and run against real pipes and processes: **4 passed, 0 failed**. (b) Hosted: run `45132484092` (`81fd847`) — all three job pages report `completed successfully`, including job `137550925338` (`Native policy and one-use action tests`, zero failure markers); the run page shows no failure. That is the first green native job in this branch's recent history and the first compile-and-test proof for any commit after `c00e35a`.

**Second fix this session (`3f4e3df`).** `conversations.start_turn` registered the turn and inserted the assistant row as `queued` before asking the runtime for a thread; a refused thread (`RuntimeError`) escaped with the claim and the row in place, so the conversation refused every later turn and held one of the two inference slots until restart. The claim and row are now released, the row is marked `error` with an actionable reason and the route returns a `ValueError` instead of a bare 500. The new test fails on the old code (the `RuntimeError` escapes); `tests.test_conversations` 26 tests pass, and the full suite is **416 tests, OK, 4 skips** with `PERSONAL_CODEX_HTTP_TESTS=1`. Frontend: `41 tests / 8 files` pass and `tsc -b` is clean. Run `45134310109` (`3f4e3df`) reports backend, frontend and native all green.

**Still not claimed.** No real-UI macOS acceptance ran here (this host is Linux with no `swiftc`, `xcrun`, `codesign` or `osascript`), so R-01 and R-05…R-10 stay blocked behind the owner's runbook. A green native CI job proves compilation and policy tests, not a permissioned window session.

## 22 November 2026 — CI re-check and full-task lifecycle re-audit

Continuation session; nothing was restarted. The primary checkout stayed on `personal-codex/stabilization` at `12a24d5` with its user modification (`web/style.css`, sha256 `4746cdd0…` unchanged) and its preserved untracked files, and feature work stayed in `.worktrees/mac` on `personal-codex/mac-automation` at `999f591`.

**CI.** The branch's workflow-run list still serves a stale cache: it shows #50 (`f26ae74`) and #51 (PR #2) as "in progress" and lists no run at all for `999f591`, `6e919cd`, `54cbdad` or `ad2cec0`. Job names and logs remain unreadable from this host (the REST API answers 403), so no CI result is claimed for those commits. New evidence on the two earlier failures: runs #44 and #45 **are the same commit** `294f4e6`, once from the push event and once from the PR synchronize event, and both failed. That rules out one flaky run, but the failing job is still unnamed; they stay unexplained, not resolved.

**Lifecycle re-audit (preparatory risk reduction, not acceptance).** Read end to end with no change-worthy defect found: `app/project_agent.py` (`start`, `_supervise`, `_run`, resume and delivery paths), `app/full_task.py` (`parse_plan`, `requirements_feedback`, `test_count`, `verify`, `deliver`, `markdown`, `proposal_cycle_period`), `app/project_review.py` (`review`, `apply_new`, `apply_verified`), `app/task_backend.py` (`plan_task`, `execute_task`, `inspect_task`, `resume_task`), the `/api/full-tasks`, `/api/tasks/<id>/full-resume` and `/api/tasks/<id>/autonomous/*` routes, and `Store.recover_interrupted`. Behaviours specifically checked and already guarded: the single-run slot is released outside `_run`; a restart closes the in-flight `autonomous_runs`, `tasks`, `proposals` and `rounds` rows; resume re-binds provider identity, destination inode identity and Git baseline; delivery refuses conflicting destination edits and re-checks digests after its preflight; the 18-round lifetime budget is enforced before any write; identical proposals and exact cycles of period 1–3 are blocked only when they make no content progress. Per the session rule against manufacturing work, no speculative change was made to these paths.

**Verification actually run this session.** Backend `415 tests, OK, 54 skips` (35.1 s, exit 0, `PERSONAL_CODEX_HTTP_TESTS=0`); frontend `41 tests / 8 files` passed; `tsc -b` clean. No macOS check ran: this host is Linux with no `swiftc`, `xcrun`, `codesign` or `osascript`, so the real-UI Phase 1 items (R-01, R-05…R-10) remain unrun and unclaimed.

## 20 November 2026 — Mac actions and repository polish

Added a local native Mac actions capability with bounded installed-app metadata search, Finder selection, canonical identity revalidation and explicit expiring one-use confirmation. The opener uses fixed arguments, no shell/scripts/backend transport and a filtered environment. Credentials/scripts/symlinks/stale choices are refused. General cross-app automation remains unimplemented.

Seven Rust tests, fourteen frontend tests, TypeScript/Vite and the optimized13.35MiB app build passed. Strict ad-hoc signature verification passed; no notarization. The native UI connector stalled for4404seconds despite a requested15second timeout and returned an expired continuation. Visual acceptance is blocked and was not claimed. Earlier frontend build caught a missing JSX brace; it was corrected before the successful build.

Refreshed README, native/setup/Mac-action guides, documentation index, current implementation matrix, task list, contributor/PR guidance and pinned read-only GitHub Actions checks. Audited26unpushed commits/379unique blobs for private target literals and credential/private-key shapes: no matches; this is not a complete DLP guarantee. Protected diagnostic remained unread/unstaged.

Read-only JARVIS test resolved private DNS and connected dashboard80;443/8787refused. No credentials, HTTP/inference requests, SSH commands or target changes. Remote integration remains unaccepted. Publication was authorized by the owner's new request; actual synchronization/CI status is recorded separately after execution.

## Hosted verification follow-through

The first published source9d2de2d passed GitHub's frontend and macOS native jobs. Its Linux backend job found a fixture assumption: the process-readiness test inherited the production200GBfree reserve. Only the disposable test subprocess now explicitly uses1GBreserve/5GBdata admission; production limits and dedicated low-space tests are unchanged. The six affected runtime tests passed locally after the fix. The follow-up f2ea8e7 source passed all three hosted jobs in run44749454322: Linux backend377discovered/363passed/14optional-or-platform skips(63.188s), frontend and macOS native. Both remote branches match that source. The repository description/topics were updated without changing access or visibility. Current operations/security/container guides now replace old untested-image and74GBinitial-allocation claims with actual scoped proof and the strict24GBdata/25GBtotal contract.

## Native fixture concurrency correction

The documentation-only follow-up5334804 passed all jobs on stabilization, but its parallel main run exposed a timestamp collision between native test fixture folders. The failure occurred during exclusive temporary-directory creation, before any opening action. Fixture allocation now includes a process-local atomic sequence and bounded exclusive-create collision retries; production action code is unchanged. All seven native tests passed again, then all20parallel repeats (seven cases each) passed. Fresh hosted verification follows the fixture-only correction. Both original failing runs remain visible; no assertion or action permission was removed.

## Earlier verified milestones

The remaining entries are historical evidence. Current status and NEXT_SESSION_PROMPT supersede their older pause, source, deployment and publication claims. Full original content remains in Git history.

## Bounded proposal cycles and owner-dashboard review — 2026-11-20

The mission is active after the user's latest “it's back”; older pause sections are historical. Shared native/full-task execution now stops exact proposal cycles of periods1–3 before a repeating proposal executes. Only96recent evidence rows/six identities are considered; real content changes reset multi-step history, no-op writes do not, and legacy successful edits are conservative boundaries. Cycle period and a content-progress bit persist alongside existing content-free proposal identities. No semantic-loop claim or new content logging; periods greater than3 and changing-output cycles remain outside this guard. Existing scope/approval/cancel/resume and lifetime budgets are unchanged. See docs/AGENT_PROGRESS_GUARDS.md.

Backend377discovered/372passed/5skipped(70.115s). Six new guard cases first failed against the absent function, then passed. Actual authenticated loopback/macOS-sandbox deterministic scenarios blocked period2after4implementation proposals and period3after6implementation proposals; immediate repeat still blocked after2implementation proposals. A normal multi-round repair still delivered verified code. The first ordinary test attempt lacked local socket permission; rerun under authorized test permissions passed. Failed logs are retained. No model calls, target commands or frontend changes in this increment.

Exact committed runtime282b90d759c2cf76e3306fe87ee6a1f74f7922f2 now passed17container checks in42.435s in the disposable Linux guest. Minimal context SHA256f440733284af9f5da02f2d3e5a7275e7fddd719120c1936ffde41eeb97bd89e6; resulting local image sha256:6e93d5296b60fd6eec7e781391b57590c4a147e0db87c84dba8d0e66b134bd0f. Actual FTS5/index/attribution/remove, cycle guard/progress boundary, credentials, no-connect/disabled execution,512MiB/1CPU/PID bounds, readonly/dropALL/NNP, mounts and persisted restart were verified. Idle21.46MiB/one process; clean container exit0/noOOM. Guest snapshotted/stopped. No target or user-namespace/coding-executor certification; fixture capacity reserve1GB differs from unchanged production200GB/24GBdata settings. Earlier baa4e4a16check/5ec6f4c13check receipts remain historical.

Read-only JARVIS dashboard review confirmed the existing local owner account and installed1.6.2 Custom App → Import → Compose/DockerCLI route. Only blank forms/visible hardware/storage metadata were inspected, no Submit/Install/file upload or settings/service change. Rounded storage is not exact admission proof. Public related CasaOS source raises pull/path-creation concerns but is not established as the installed binary. Numeric ownership, image build/load and preservation of every hardening field remain unverified. Current private ZIMAOS_ADMIN_METHOD_REVIEW.md and JARVIS_DASHBOARD_READONLY.json supersede old “role unknown” claims. Original user tabs were not navigated; closure of only the new inspection window was requested but could not be confirmed after connection timeout. Do not blindly close more windows.

No JARVIS write, privileged workaround, password/key extraction/reset, declined probe, Serve/policy edit or publication. Do not ask again for the unknown passphrase. Preserve protected diagnostic unread/unstaged, profiles, user Ollama and old release bundles. Continue local reliability work and resolve installed-version/ownership/family-preservation gates before requesting concrete installation approval. The full mission remains partial.

## Attributed document search verified — 2026-11-20

Opt-in project document search is integrated in native Workspace, offline project chats, full/native coding calls and manual approval-bound prompts. It uses only selected imported excerpts, scoped SQLite FTS5, source/excerpt/chunk hashes and offsets; no source-file/server scan, model, embedding download or extension loading. Explicit owner add/update/remove actions, bounded literal queries, transactional reindex, stale/tampered/credential-like omission, caps and untrusted-reference labeling preserve memory/approval boundaries. See docs/PROJECT_DOCUMENT_SEARCH.md for exact behavior and limits.

Full371backend discovered/366passed/5skipped(64.780s),16new cases; frontend12/TypeScript/Vite and native build passed. Actual deterministic HTTP/macOS-sandbox task proved references entered planning/implementation prompts(1.15s). Independent six-topic lexical evaluation P@1/MRR1.0 plus isolation/stale/removal negatives; not a semantic or live-model quality claim. Native chooser/add/search/hash/range/remove/empty-result checks passed in the preserved separate profile after UI automation expired and reset recovered. User browser and preexisting Ollama were untouched; helper owned only backend/app and read model metadata. Both owned processes stopped. New strictly ad-hoc signed13.15MiB bundle is data/document-search-app/Personal Codex.app; launcher prefers it, retaining all older bundles/profiles. Initial unsigned staging copy was explicitly signed before verification; no notarization claim.

Earlier exact5ec6f4c API container passed13checks in18.827s in the disposable guest, then guest snapshotted/stopped. The document-search source needs its own committed context/container acceptance next. JARVIS remains online but local SSH agent empty at refresh; no authentication attempt, target command/change, policy/Serve action or publication. Do not ask for the unknown passphrase again, extract/reset credentials, use target privilege workarounds or revive declined probes. Continue the same master mission and preserve unread/unstaged diagnostic, histories and separate-browser preference.

## Resumed by user — 2026-11-20

The new user message “it's back” fulfills the second pause below. All98saved artifact hashes and the full Git bundle verified; entry HEAD40f572c, tracked tree clean, implementation5ec6f4c retained. Protected diagnostic remains unread/unstaged. Current private resumed-mission-2026-11-20/RESUMED_STATE.json is active; old pause/checkpoint records remain historical. Resume the same master mission. Next: exact5ec6f4c container verification in the dedicated disposable guest, then remaining local engineering and authenticated target/preservation gates. No JARVIS write, privileged workaround, credential guessing/extraction, declined probe or live policy/Serve change is authorized by the trigger. Preserve current user browsing; use separate windows or hidden in-app browser.

## PAUSED BY USER — second safe stop, 2026-11-19

**Do not continue this mission, start services/VM, contact JARVIS, run engineering tasks or poll until a future user message explicitly says “it's back”.** The latest user request quotes that phrase only as a future condition. No automation is scheduled. This pause supersedes every active/next-action section below.

Verified implementation5ec6f4cd26a2cf21684eb776616dc8bc798781f5 on personal-codex/stabilization is preserved; this documentation-only pause commit follows.355backend discovered/350passed/5skipped(74.501s),10frontend tests/native build, real9BCLI and existing-project ML repair,12independent ML checks/artifacts/corrected frontend are saved. Read docs/ML_WORKFLOW_ACCEPTANCE.md for scaffold authorship, failed attempts and corrected weak fairness test; do not claim universal or blank-project full-generation success. No JARVIS deployment/change or publication.

Private current-chat outputs/safe-stop-2026-11-19-2 contains SAFE_STOP.md/state, consistent SQLite backup(integrity_check passed), synthetic project/workspace archive, full Git bundle and artifact hashes. All profiles, bundles, delivered/uncommitted fixture files, tests, artifacts, histories and model cache are retained. Owner token stays in its original private file; protected user diagnostic remains unread/unstaged/unchanged and excluded from archives. No reset/clean/delete.

Task-owned native app/backend/Ollama/test server and QEMU stopped; listeners8787/8799/11434/22291 absent. Hidden in-app test tab closed; user's browser untouched. Guest checkpoint/private restart metadata are saved; original and newer overlays remain. Final5ec6f4c source context was prepared, but automatic approval review rejected its pending container verification because this pause became active. It did not start and must not be retried during pause. Earlier13container assertions passed on a4276b4 in the disposable guest, not JARVIS.

After the future trigger, first verify saved state/manifests/bundle, actual branch/HEAD/tree and concurrent user changes without accessing the diagnostic. Resume the same master mission from current source and saved evidence. Next work is final source-specific disposable-container acceptance, then remaining native/remote acceptance and authenticated/operator/family-preservation gates. Do not repeatedly request the unknown passphrase, guess/extract/reset credentials, retry unchanged keys, use JARVIS privilege workarounds or revive declined probes. Use separate windows or in-app browser. Do not apply policy/Serve changes from stale/gated candidates. Preserve all functionality and safe-stop instructions across context/account changes.

## Verified ML repair and runtime follow-through — 2026-11-19

Latest backend regression355discovered/350passed/5skipped,74.501s;6new sequential-patch tests,6planner-reference tests and the final-review prompt test pass. Four deterministic delivery scenarios passed: new1.20s/existing1.22s/conflict1.74s/cancel-resume1.52s. Sequential patches are bound/reviewed against projected incoming bytes, retaining digest checks at every actual write, external-change refusal and exclusive creation. Web review labels those hashes as before-this-step. No permission or production execution gate was relaxed.

The real9B statistics task passed after resume with unchanged tests. The complete synthetic ML scaffold now also has an actual9B-maintained delivered project,12independent tests, CLI smoke, model-artifact prediction/hash verification and corrected frontend visually checked in a separate hidden in-app tab. Final fairness repair3rounds/75.619s. Read docs/ML_WORKFLOW_ACCEPTANCE.md: trusted scaffold authorship, failed absolute-path attempts, sequential-hash/review/planner repairs and the weak initial fairness test/false-positive acceptance are all explicit. Three new discriminating fairness cases first failed against delivered code, then passed after the agent repair. Do not claim blank-project full ML generation or universal reliability. Runtime artifacts are generated by the explicit documented command, not automatically copied by source delivery.

Native test profile/projects/history/failed worktrees/artifacts remain private and saved. Our native app/backend/Ollama launcher and synthetic frontend server were stopped cleanly after completed tasks; no polling/automation. The Linux verification VM remains snapshotted/stopped pending source-current container follow-through. Local access refresh: Tailscale Running/JARVIS online, existing SSH agent empty. No SSH auth attempt/target command/configuration/Docker/Serve/policy change or publication. Do not ask again for the unknown passphrase or revive declined probes. User's browser was untouched.

Continue the full master mission from actual Git HEAD, not older checkpoint hashes. Source-current image/context and fresh target authentication/operator/preservation gates still determine deployment; prior a4276b4container evidence is exactly scoped. Remote full acceptance, production quota/recovery scale/OS executor and broader native dependencies/visual-generation remain open. Preserve unread/unstaged diagnostic and all old profiles/bundles/history.

## Resumed runtime verification — 2026-11-19

Verified source a4276b4 adds model metadata and content-minimal inference observations. The later proposal/context reliability repair passed342Python discovered/337passed/5skipped in79.107s, plus5focused proposal cases and a real HTTP/macOS-sandbox identical-invalid-proposal scenario (1.2s). Explicit task paths are ranked ahead of incidental references; large relevant files now contribute bounded UTF-8 snippets instead of being silently omitted below the default4K snippet size. Two new context regressions cover this. Repeated identical tool operations are compared before binding/execution, including invalid proposals; cosmetic summaries do not evade identity. This is exact consecutive repetition detection, not general semantic/cycle reasoning.

A real installed9B task initially exhausted6rounds on malformed/wrong-path/create-over-existing proposals (58.009s); guards preserved the original files. After clearer complete-envelope/actual-path instructions, explicit resume delivered the corrected CLI and README in3more rounds/27.253s. Independent smoke returned4.0; original tests unchanged. Native UI visibly displayed real call4.48s/first text0.15s/provider-reported584input/100output/22.53tokens/s. These are an observed call, not a hardware benchmark or universal throughput claim.

The exact a4276b4 minimal context built offline against the pinned base in a separate Debian VM.13container checks passed: owner/worker boundary, disabled execution/direct-provider refusal, exact synthetic proxy authority, actual512MiB/1CPU/128PID/read-only/drop-all/NNP constraints, PID1two seccomp filters/zero effective capabilities, dedicated mounts, authenticated readiness and conversation persistence across clean restarts. Idle21.08MiB; clean exit0/noOOM. A harness response-shape mistake was corrected and failed logs retained. No JARVIS/Serve/HTTPS/ACL/container-executor/user-namespace acceptance is implied. Guest has identity UID mapping and cannot certify the coding executor. It is snapshotted/stopped with original overlay/history retained.

Synthetic ML scaffold has9independent tests passing normally(0.483s) and through the app's read-only command sandbox(0.476stest/3.451swall), including model-artifact prediction round-trip. Five separate bounded stress cases passed in1.285s. A9Brepair task against two deliberately broken production functions stopped on repeated absolute-path proposals after3rounds/98.818s, without delivery. Keep this failure; do not claim complete realistic ML agent acceptance. Scaffold was authored as a trusted benchmark, not entirely generated by the model. Frontend/browser and independently exported artifacts remain pending for that live repair.

No JARVIS command/change, publication or diagnostic access occurred. Current private receipts/logs and live processes are in resumed-mission-2026-11-19. Separate native verification launcher owns127.0.0.1:8787/11434; no model invocation should be left running across a user pause. Read actual Git status and private runtime state before continuing. The mission remains partial; remote authentication and preservation gates remain unresolved. Earlier pause sections are historical after the user's “it's back”.

## Resumed model observations — 2026-11-19

User's explicit “it's back” resumed the paused mission. Verified saved hashes, preserved the diagnostic/branch and restored only the saved draft after comparing runtime files with95ed914. Added bounded attributed model metadata, monotonic/first-text timings, explicitly provider-reported usage, content-minimal native task evidence and visible native settings/evidence components. No dependency, automatic routing/cloud fallback or prompt upload.16new backend cases/full335(330pass/5skip),10frontend tests/build, four HTTP/sandbox lifecycle scenarios and optimized/signature-verified native build passed. Native authentication and real installed-model settings were manually verified in a separate disposable profile; UI automation initially expired and recovered after reset. A frontend command initially ran from the wrong directory and failed before tests; logs retained, rerun from desktop passed. See MODEL_OBSERVATIONS.md.

Separate project-only Debian VM cold overlay resolved the saved firmware stall. Actual x86_64 Linux network-policy13tests passed, including real filter installation/inheritance/accepted HTTP; kernel6.12.117/Python3.13.5. Docker26.1.5 and AppArmor/seccomp/cgroupns metadata observed; pinned official Python base pulled inside that disposable guest only. No JARVIS authentication/command/configuration or denied probe; existing agent remains empty. Original VM snapshot/key retained, no host mounts. Further image/native/live/ML acceptance remains separate.

## Safe pause requested — 2026-11-19

User takes JARVIS offline and requests no continuation until a future “it's back.” Saved unverified observability diffs/full files/hash-verified archive outside Git, restored only our three runtime edits to verified95ed914, retained the untracked draft module and protected diagnostic. No functionality/data reset or publication. Paused/snapshotted the disposable Linux guest and exited QEMU; disk/snapshot verified, loopback listener removed and bootstrap controller stopped. No JARVIS command/change or credential reset. Read NEXT_SESSION_PROMPT/docs/PAUSED_CHECKPOINT before resumption; no background availability polling or automation.

## Shared native task lifecycle — 2026-11-19

The actual full-task/command-runner routes now use one versioned plan/execute/inspect/resume interface. Metadata planning is read-only and detached from mutable caller dictionaries. Execution rechecks destination/provider/baseline, and the existing engine refuses resubmission of a consumed full-task plan under its run lock. Full-task resume retains persisted scope and new scopes bind provider metadata. No second engine, plugin dependency or production execution mode was added. See `docs/TASK_BACKEND.md`.

Sixteen new scope/policy/confirmation/replay regressions passed. Full backend319discovered/314passed/5skipped,61.886s; all four actual HTTP/sandbox fixture scenarios passed (new/existing/conflict/cancel-resume). A first harness invocation lacked its local parent directory and failed before product startup; retained and corrected. Frontend source unchanged. Tailscale now Running and JARVIS reachable, but the SSH agent remains empty; ordinary automatic Keychain unlock found no usable saved passphrase. Existing Zen and standalone ZimaOS sessions both require sign-in; no credentials guessed/submitted. User says passphrase is unknown: stop asking repeatedly, continue independent engineering. Use separate browser windows/in-app browser; do not interrupt the user's active browser.

## Master mission audit and memory integrity — 2026-11-19

Recovered the complete current handoff and branch at24014bf, preserving the diagnostic and all later Mac-agent work. Inspected OpenJarvis427c2dd as separate source-only reference; no dependency or upstream runtime was imported. Added source comparison, dependency-ordered roadmap and an architecture decision retaining the native Personal Codex runtime. Remote deployment remains explicitly approval-gated.

Reproduced nine existing memory defects, then repaired shared admission, truthful provenance on edit/retrieval, reviewed-digest validation, transactional promotion and the shared project cap. Added fourteen regressions including SQL rollback, competing decisions and the last-slot race. Existing user records are not migrated or silently deleted. A test-fixture token-length mistake produced nine setup errors before correction; that failed log remains separate from the nine reproduced product failures.

Fresh final backend303discovered/298passed/5skipped,64.053s; frontend7passed/build passed; cached Rust3passed. Deterministic full-task acceptance passed in1.84s before the memory edit. No live model, native UI, Docker, Linux filter or remote acceptance claim. Tool-visible agent/Tailscale state still reported empty/Stopped after owner confirmation; Terminal-state clarification requested, no SSH authentication attempted. No server/Serve/policy mutation or publication. Full details in `docs/MASTER_MISSION_TEST_REPORT.md`; private metadata/evidence stays outside Git.

## Full task execution — 2026-11-17

A single scoped authorization now covers planning, implementation, contained tests and build checks, repair, final review, and delivery. The desktop reports real progress and exposes Finder destination selection, multiple attachments, cancellation, recovery, and exact commands. Scope is persisted with the approved directory identity and baseline revision. No validation succeeds on test-only edits or a test run with zero passing tests.

On the Apple M3, a real `qwen3.5:9b` run with Wi-Fi disabled delivered source, tests, and README in 69.74 seconds. Both unit tests passed. Direct runs from the delivered folder printed 5 for addition and 12 for attachment-driven multiplication. Earlier live attempts exposed missing README handling and loss of repair evidence after rejected model responses. The workflow now generates missing standard documentation and preserves the latest verification output. Synthetic runs exercised real test failure and repair, modifying an existing project, conflict refusal, and cancel/resume.

The prior 8K model benchmark remains the basis for keeping the primary model and existing 14B fallback. The recorded offline run is one small end-to-end task. Broader dependency provisioning, live web application checks, and full dataset processing remain open.

## Native local coding agent — 2026-11-17

Created explicit Finder authorization for new folders and existing repositories. The app shows the resolved destination and authenticates the native selection through a scoped loopback request. Git initialization and registration happen inside the app, and stored native scope is tied to directory identity.

Added a bounded resumable coding loop, atomic UTF-8 file creation with nested directories, hash-bound patching, local attachment extraction, exact validation, Git diff review and application of approved additions into a previously empty project. The Mac process runner denies network access and restricts file access for autonomous validation. Existing manual offline commands also use the contained runner in the native profile.

Verified project creation, real generation, approved validation, a reviewed diff and applied files through the native desktop. Real model runs also repaired a failing existing Python repository and implemented synthetic requirements from a selected PDF and screenshot OCR. A physical Wi-Fi-off run completed real file creation, validation and review/apply. The installed primary remains `qwen3.5:9b`; the existing 14B model also passed the creation task with longer latency.

The release has bounded capabilities. Its command runner covers exact local validation and its image pipeline extracts text. The release report records remaining tool, workflow and verification gaps.

## Offline hackathon workstation — 2026-11-17

Added an opt-in inference policy for the two installed Qwen tags at the exact Ollama loopback origin. Existing local provider transports enforce the offline model boundary and include the current 8K request options. The launcher manages the existing binary with cloud disabled, a single runner slot, an authenticated loopback backend, a private data directory, and the built Tauri app. The local native session uses the owner file through Rust IPC, shows its actual provider and tag, and suppresses remote setup controls. Existing round and test approval checks remain authoritative.

On the 16 GiB Apple M3, `qwen3.5:9b` (local ID `d63f830f28d5`, MLX NVFP4) scored 8/10 at 5.06 median tokens/sec and peaked at 9.00 GB of Ollama-reported residency. `qwen2.5-coder:14b` scored 4/10 at 2.80 tokens/sec and peaked at 10.29 GB. Selected 9B and retained 14B as a manual alternate. Tested 8K. System swap growth warranted leaving 12K untested.

Verified real code, Stop and next-turn recovery in the native UI. Wi-Fi-off checkpoints covered cold startup and a real streamed Python response, cancellation and recovery, persistence after restart, a native Ollama function call, and an approved local unit test. Wi-Fi came back during a longer attempt, so the remaining milestones used separate timed windows. The original Wi-Fi state was verified after the last window. A separate real-model code round applied a reviewed patch, ran its test in the task worktree and persisted the evidence-backed result.

Regression totals were 289 Python tests (284 passed, 5 skipped), 7 frontend tests and 3 Rust tests. Built the optimized Tauri app from cached dependencies and verified the locally signed bundle. The installed ML packages passed a synthetic fit, prediction and plot.

## Mission 1C.1 production policy engineering

Refreshed authorised SSH/device/model metadata privately; daemon socket still denied, existing operator/current policy pending. Added worker-only registration/stored discovery/chat/round/invocation gates, additive Linux x86_64 synchronised no-connect filter and status/acceptance checks. Initial data admission24GB within25GB total target; no hard quota. Filter also blocks Fast Open/sendmsg/sendmmsg, unsafe socket creation, io_uring and cross-process FD/memory routes; startup tests fail closed. Kernel runtime proof pending separately approved transient probe, no host firewall/daemon mutation.

Final286 discovered/281passed/5skipped60.050s, zero failures/errors. Earlier285/280pass/5skip60.775s predates Fast Open correction. Initial probe fixture child-string syntax error fixed locally; synthetic client/HTTP fixture passed before approval request. Revised unexecuted probe supersedes its earlier hash; no server install/write/credential/service/network/deployment or publication. See current handoff for exact pending decisions.


## Read-only infrastructure review completed — 2026-11-07

The user unlocked the existing SSH identity. Normal authorised metadata inspection succeeded through that agent, with strict existing host verification and no forwarding/private-key read or SSH/agent change. SSH is resolved; old empty-agent/diagnostic/review-block descriptions below are historical. Do not repeat the consumed public-identity diagnostic or ask for another unlock while access remains usable.

Exact target/account/kernel/storage/DNS/TLS receipts remain outside Git. Docker daemon/Serve inspection is blocked by current socket permissions; do not use sudo, group/ACL changes or an alternative privileged API. Obtain an already-authorised operator's scoped read-only receipt. Kernel prerequisites were observed, not container enforcement. Private DNS resolves; private TLS connection was refused, so no certificate/Serve readiness is claimed. Full current tailnet policy and family/admin relationships remain missing.

The old application parent is replaceable by other users. New proposed root `/DATA/PersonalCodex` requires approval; nothing was created or changed. Preflight now checks every ancestor's ownership/writability/sticky policy before credentials. Numeric identity remains a candidate until actual userns mapping is known. AppArmor prototype now accepts only enforcing mode. Deterministic minimal build context comes only from reviewed committed Git objects, with no untracked files or runtime/diagnostic content. Context reproducibility is not image reproducibility.

Final relevant regression: **276 discovered, 272 passed, 0 failures/errors, 4 skipped, 59.544s**, HTTP profile. Three optional disabled gateway tests and one Linux/proc observation skip on macOS. Eight new regressions cover ancestor boundaries, deterministic committed-only context and AppArmor enforcing labels. No real Linux/Docker enforcement passed. Historical Qwen worker19/19, recovery6/6, frontend7/Rust3 remain historical and were not repeated for these changes. No new native binary or remote end-to-end proof.

Private `JARVIS_FINAL_APPROVAL.md`, `JARVIS_VERIFIED_READONLY_FACTS.json`, operator checklist and final artifact manifest supersede previous private queue/access/path assumptions. Final reviewed source commit/context/archive hashes are in that manifest; use git log for current tip. No server installation, directory, permission, Docker/network/Tailscale change, backup traversal, persistent Mac worker or publication occurred. Coding stays disabled. Mission1 remains partial; final installation readiness depends on the operator/policy receipts, explicit phased approvals, real image/runtime/HTTPS/remote acceptance and the documented recovery/storage limits.


## Approved public-identity diagnostic completed

Following explicit user approval, exactly one public-key-only SSH handshake established connectivity, matched existing host trust and received server public-key acceptance. Signing/agent/password authentication remained disabled; expected authentication failure, no remote command/private-key read/configuration change. Approval consumed; next is user-controlled existing-agent unlock, then already-authorised read-only inspection after access changes. No code changes or new regression claims; historical Mission1B test results retained.

## Mission 1B security, recovery and isolation prototype — 2026-11-07

Added durable worker claims/rotation, strict schemas/clock/chunk bounds, descriptor snapshots, encrypted offline recovery with stale authority revocation/locked restore, production admission/SQLite cap, operator-only no-mount/no-network executor prototype/supervisor, official public image digest lock and read-only runtime/HTTPS checks. Actual Qwen worker19/19 in46.418s; encrypted recovery drill6/6 (tiny fixture9ms checkpoint/10ms restore). Final full suite268 discovered: HTTP264pass4skip59.754s, default213pass55skip22.517s; frontend build/7Vitest/3Rust passed. No desktop source change or new Linux/container/native remote proof.

SSH local agent had no identities; no private key/config/agent change. Additional public-only handshake was rejected by automatic approval review for repeated attempt without an access change; it never ran. Pending explicit decision/access change; independent engineering continued. No JARVIS write/command, software/model download, service/Serve/ACL change or publication. Initial recovery fixture8setup errors fixed missing ledger round_id; metadata307failedclosed then exact no-auth CDN redirect handling verified digests. Full recovery64MiB limit, actual Linux isolation, broker integration and remote/policy/storage gates remain explicit in current handoff.

## AFK final preparation and client verification — 2026-11-07

Saved core milestone 9109eb1. Added browser cookie sign-in/sign-out and capability gates, private rotating worker logs, snapshot concurrency/incomplete-inventory refusal, installed-model readiness, duplicate security-header rejection, bounded escaped-Unicode worker envelopes and total control deadline. Final review also blocked code proposal/patch endpoints in disabled profile and revalidated persisted project/workspace roots. Added targeted regressions for each boundary. Prepared Docker/Compose/LaunchAgent/environment/build allowlist/read-only preflight/ACL fragment and recovery/API documentation. No production mutation.

Actual optimized native client authenticated, showed installed worker model/MAC, streamed real Gemma answer and stopped a second generation; DB confirms complete/cancelled worker states with cleared payload. Browser invalid/valid login, execution controls and logout verified. Synthetic service stopped and native disconnected. No private model input beyond synthetic fixtures. Full final test counts/timing are recorded in NEXT_SESSION_PROMPT.md and the local AFK report.

A rotation test caught reopened log files at 0644; custom private opener fixed and passed. An unprivileged default suite invocation hit 37 local-socket permission errors; authorized loopback rerun passed. Additional Unicode/slow-drip and disabled-profile/path tests pass. Do not obscure failed evidence or claim Docker/JARVIS integration from static tests. All live server deployment actions remain approval-gated.

## 2026-11-07 13:14 IST — AFK implementation checkpoint

Audited backend and created docs/IMPLEMENTATION_MATRIX.md. Implemented trusted Serve metadata only with explicit private origin, loopback proxy and owner auth. Added inference.py/mac_worker.py scoped outbound-poll worker; fixed silent HTTP/1.0 stream cancellation after two new tests exposed detached sockets. Added readiness, instance lock before lazy recovery, bounded clients, SIGTERM chat draining, private new database files and disabled all repository processes in the safe Serve profile. Last full 205-test suite passed with 4 skips; focused runtime six passed; frontend build/seven tests passed. Real Qwen worker flow: 17 checks, 82.764 s, actual patch/test/completion/restart, original fixture unchanged, no private code/model downloads/inbound listener. First fixture attempt correctly refused a different test-directory command; aligned fixture with tests/ and asserted one real executed test. Retained failed evidence. Noninteractive SSH with dedicated key rejected; no server command or mutation occurred. Continue deployment/browser/native finalization without asking absent user for ordinary decisions.

## 2026-11-07 12:10:46 IST — JARVIS readiness reconciliation only

Read the new user directive and current repository handoff/README/architecture/security/deployment/threat/acceptance notes. Git at entry: stabilization `4a3ea1d91e70e392faf342ea03b335d7f207169d`, tracked/staged tree clean, only user diagnostic untracked; diagnostic contents were not read. New user evidence establishes dedicated passphrase-key SSH, measured ZimaOS hardware and existing container/network prerequisites; previous default-identity rejection is historical. Intended architecture changed to Mac inference plus JARVIS localhost API behind private Serve. No implementation/deployment or Mission 2 changes were started.

Reran security/auth HTTP fixture suite: 11 tests, OK, 3.347 s. Reran backup/restore suite: 4 tests, OK, 0.075 s. Historical total remains 177 discovered; no full-suite/native rebuild was repeated because runtime code is unchanged. Synthetic origin/authority checks returned `Unrecognized Host header` and `Cross-origin requests are not allowed`. Compared with official versioned Tailscale v1.98.3 reverse-proxy source (incoming Host preserved, HTTPS metadata forwarded): current direct-listener contract needs safe trusted-proxy support before Serve deployment. Existing local-provider transport also does not provide a JARVIS-to-Mac inference route. These are identified readiness gaps, not remote tests or implemented fixes.

No DNS lookup, remote SSH check, container/Serve/ACL/storage inspection or server mutation was performed in this pass. Exact private supplied inventory and the first pending Mac DNS command saved outside Git. User requires one command, explanation and result at a time; final response supplies only the system-resolver lookup, then waits. Directory ownership/creation, package/service/container changes, Serve, ACL/SSH/firewall changes and downloads remain approval-gated. Updated documentation locally; no commit/push at this readiness step.

## 2026-11-07 — actual Mac implementation session

Implementation committed as `c5e34159faf5c88bcfc1163e37c0ddffffebacce` on `personal-codex/stabilization`; a documentation checkpoint follows. Remote branch was rechecked before publication and remained at `12a24d5`. Main was not merged or modified. Private server target metadata was excluded from Git and retained in a local-only deliverable.

Located the existing Mac checkout at the historical path. Initial branch was `personal-codex/stabilization` at `414e0cb`, with only the user's untracked `personal-codex-diagnostic.txt`. Verified remote heads without stored Git credentials: main still `3ab25b0`, stabilization had advanced to `12a24d5`. Fetched and fast-forwarded stabilization; no reset, clean, branch merge or user-file overwrite. The initial HTTP-enabled 156-test run failed one test that assumed Ollama was offline; the already-published remote fix isolated its unreachable endpoint. Reconciled baseline: 156 discovered, OK with four skips.

Sandboxed loopback operations initially failed with PermissionError; authorized out-of-sandbox loopback tests passed. Mac: Darwin arm64, macOS 26.6, Python 3.13.9, Node 24.22.1, Apple Command Line Tools installed; Rust/Cargo initially absent. User explicitly approved project dependency downloads and an isolated Rust toolchain. Installed stable Rust 1.99.1 under this chat's `work/toolchain`, without changing shell profiles or global toolchains. Pinned npm/Cargo locks; two compilation jobs; no inference engine or model downloads. Mac free storage was roughly 73 GiB initially and around 71 GB during later diagnostics; the Mac uses a 5 GB reserve while Linux defaults to the required 200 GB, both configurable.

Tailscale 1.98.10 reported Running, Mac online, JARVIS online/active at `<server-tailscale-ip>`, MagicDNS `<server>.<tailnet>.ts.net`. User confirmed JARVIS as ZimaOS, user `<ssh-user>`, home `/DATA`, and authorized read-only SSH only. SSH with existing host trust, BatchMode and no TTY reached the server but returned Permission denied (publickey,password). No credentials were invented or printed, no server inventory was obtained, no settings/services were changed and no backup directory was accessed. Prepared `scripts/inspect_host.sh`; actual server hardware, Docker/service support, model installations and storage remain unknown.

Implemented the native client and vertical backend slice documented in the current status. Privacy review found the newer conversation code silently generated an approved network record for cloud chat; replaced it with explicit refusal. The optional gateway's local hop could lead to external routing, so default-disable it and require network approval when enabled. Corrected capability metadata that advertised unimplemented native tool calls. Added owner authentication/private TLS policy, body/origin protections and token-safe logging; fixed concurrency/cancellation/recovery edges and added verified snapshots with storage guards.

Live installed-model evidence: llama3.2:3b passed JSON probe (5,186 ms), streaming probe (2,031 ms, 23 chunks), real chat and correct patch/test execution. Completion failed through repeated patch proposals. The first harness also rejected harmless read-only fixture inspection; widened only its synthetic read allowlist, not patch/command policy. Qwen2.5-coder:14b completed every real authenticated fixture check: chat, approved worktree, reviewed exact patch, approved tests exit 0, model terminal completion accepted by evidence, unchanged source repo and persisted history after Store restart. Total 110,671 ms; proposal invocation 65,546 ms. This is one small synthetic fixture on the Mac, not a server recommendation or broad benchmark. Evidence files remain in this chat's outputs; no private repository prompts were sent to a model.

Actual native UI tested via CUA: app launch, history, a real streamed answer, stop status, files, round/test evidence, diff display, snapshot count 0→1, disconnect/reconnect, missing-token HTTP 401, valid synthetic owner token showing Owner authenticated, and self-signed TLS refusal with no fallback. UI review exposed unmatched-patch presentation and stale task-selection state; both were fixed and the client rebuilt. The app was left disconnected. Temporary fixture backends on 8787/8788/8789 were stopped; existing Ollama/Tailscale services were untouched.

Final Python HTTP-enabled suite: 177 discovered, OK (skipped=4), 46.327 s. Default: 177 discovered, OK (skipped=34), 20.701 s. Skips are explicit listener gates plus absent optional gateway (3) and Linux-only process inspection (1). Python compilation, dashboard JS syntax and git diff whitespace checks passed. React/TypeScript/Vite production build passed; 2 Vitest parser tests passed; Rust test passed; native app bundles built. No configured lint suite exists. JARVIS deployment, real remote/off-Wi-Fi tests, OS sandboxing, scheduled supervision/backups, peak-memory/tokens-per-second measurement and signed/notarized distribution remain outstanding.

## 2026-11-02

Reconciled the actual repository before writing code: the workspace and `origin/main` were both at `e9b0ee5` with a clean tree, while the owner's Mac report described an older local `f2fea40` that is 15 commits behind. No history was rewritten, reset or force-pushed; the correct action for that checkout is a fast-forward pull, and the untracked `personal-codex-diagnostic.txt` was deliberately not committed.

Closed the named Milestone 6 gaps in the order that unblocked the others. Cancellation first: `execute_in_workspace` used to wait for the command to finish, so a long test run ignored cancellation until it completed. It now polls every 200 ms with the existing persisted cancellation check, sends SIGTERM to the process group, escalates to SIGKILL after 1.5 s, preserves partial output, and returns exit code 130 with `cancelled: true`. The tool layer had to change too: a cancelled test command was being classified as an operation error, which made later operations `skipped` and hid the reason. It is now recorded as `cancelled`, the round stops, and the ledger matches the round result.

Live activity is backed by the existing `events` table rather than a new channel: `GET /api/tasks/{id}/events/stream` emits Server-Sent Events whose ids are SQLite rowids, so the browser's `Last-Event-ID` resumes exactly after the last delivered event. The stream is read-only, bounded to 500 events and 120 s, and closes on a dead client.

Diff review was added because approving a digest was previously an act of faith: `GET /api/tasks/{id}/agent/diff` re-resolves every pending `apply_patch` path through the workspace containment check, returns a unified diff, the digest the proposal was bound to, the file's current digest, the occurrence count, and a stale flag. `tests/test_interaction.py` first asserted a stale file only after editing it, and also covers escaped and secret paths, which is how the error path is proven rather than assumed.

Repository search reuses the context engine's walk so it inherits `.gitignore`, secret-name, symlink and generated-directory exclusions; a naive `rglob` implementation would have returned `.env` content. Finally, every response now carries a restrictive CSP (`default-src 'self'` with no inline script/style, `default-src 'none'` for JSON), `nosniff`, `no-referrer`, `X-Frame-Options: DENY` and `no-store`.

Verification: 126 tests with HTTP integration enabled, `OK`; 126 with listeners skipped, `OK (skipped=19)`; `py_compile` and `node --check` pass; loopback smoke test returns 200 for `/` and `/app.js` with the new headers. Still no live model: the cloud workspace has no Ollama binary and nothing listening on 11434, so the Mac-side harness run remains the next task. Browser-level automation is also still unavailable here, so the dashboard's new panels are covered by static contracts and HTTP tests, not a real browser.

## 2026-11-01

Verified `5e4267f` and confirmed no Ollama binary or service exists in this environment, so live model validation remains a documented, harnessed procedure rather than a claimed result. Built `scripts/live_provider_check.py` first so the owner can prove endpoint/model compatibility in one command, then made it deterministic under test with a loopback stub (unreachable service, empty model list, explicit-model requirement, valid probe, invalid JSON).

Added streaming at the transport layer (NDJSON accumulation with byte/chunk caps, cancellation, termination and malformation rejection) and kept it opt-in so the approved non-streaming path is unchanged. Provider error bodies are now scrubbed of secret-shaped strings, and provider health/latency is exposed without new network calls.

Memory promotion required the most care: the first implementation rejected every approval because duplicate detection also compared the proposal against itself. Fixed by separating "proposing" (memory + pending proposals) from "approving" (stored memory only). Two smaller bugs surfaced: provider inserts broke when additive migrations widened the table (fixed with explicit column lists), and the `.git` file/worktree marker leaked into prompt listings and context manifests (now filtered). Measured performance: context selection ~45 ms for 24 files and 42.5 kB selected, SQLite query ~0.11 ms, API responses under 2 ms. Then added OpenAI-compatible SSE streaming, stable failure classification, a single read-only discovery retry, and a deterministic completion summary memory proposal that stays pending until approved. Verification: 110 tests with HTTP integration enabled, `OK`.

Started Milestone 4 from a verified `cc334d1`. Implemented the repository context engine first because it determines prompt budget and approval binding: `app/context.py` with deterministic ranking, `.gitignore`/secret exclusion, symlink containment and digest. The round request now stores the exact approved prompt with its context so `round/plan` reproduces the approved bytes instead of rebuilding them (rebuilding would have silently broken the digest check).

Added cancellation as persisted state bound to a round, with a `stop_check` consulted before every operation and a `round_feedback` cancellation record; added an operation ledger written through tool callbacks so `app/tools.py` keeps no storage authority; added cumulative budgets with clamped environment variables and an explicit reset. The dashboard gained cancel, budget meter, ledger, and context panels.

One real bug was caught by the tests: `GET /agent/context` was initially added to the POST dispatcher, so it fell through to the static handler and returned HTML. Moving it to the GET dispatcher fixed it. Verification: 84 tests with HTTP integration enabled, `OK`; compilation and `node --check` pass.

Implemented the multi-round iterative engine on top of the existing single-cycle dispatcher. The new `rounds` table and endpoints were added without changing the existing proposal lifecycle. The first test run of the new suite exposed three missing imports in the test module and one real design bug: a non-zero test exit marked the whole round `failed` instead of `failed-checks`, which would have hidden test evidence from the feedback loop. Fixed by classifying only non-`run_tests` tool errors as hard failures, then confirming all 64 tests pass with the HTTP integration enabled. Updated the dashboard with round controls, history, and a final report, and added contract checks for the new element ids and routes. Added restart recovery so an interrupted round is marked `interrupted` instead of blocking the loop, plus a single in-flight guard in the dashboard; the suite is now 66 tests.

Environment discovered: Apple Silicon macOS (Darwin 25.6.0), Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite CLI, SSH client; Docker and Rust/Cargo were not found on PATH. Workspace volume had approximately 76 GiB free. The visible Mac address was 192.168.1.11. ZimaOS was not inspected because no server endpoint or authorization was available.

Created an isolated Git repository in this deliverable. Used no third-party runtime dependencies. Unit tests passed (4/4). A listener smoke test failed at bind time with sandbox `PermissionError`; it was not retried because policy changed neither the port nor the permission model.

Added and unit-tested a capability-gated executor. Worktree creation needs a matching approved `modify` record. Command execution needs a matching approved `execute` record, uses no shell, is restricted to a task-owned workspace, supports a 1–300 second timeout, records redacted output, and emits an audit event. UI wiring and end-to-end HTTP tests remain outstanding. An approved unsandboxed loopback smoke test later confirmed the health endpoint and dashboard respond; process was stopped immediately.

Completed UI wiring for the approval and execution workflow. Approval decisions are now immutable after a first approved/rejected decision. Node syntax validation should be run after this UI change; no automated browser or HTTP integration harness has been added yet.

Ran the updated unit, Python compilation, JavaScript syntax, and loopback asset smoke checks successfully. The loopback server was stopped after verification.

Added an opt-in in-process HTTP integration test. It creates an initialised temporary Git fixture and switches the app to temporary SQLite/workspace storage, asserts both denied pre-approval operations and allowed post-approval operations, then shuts down the server and removes temporary data. With `PERSONAL_CODEX_HTTP_TESTS=1`, all seven tests passed in 0.646 seconds.

Added execution resource caps and critical-approval clean-worktree release. The initial strict resource setup failed in this macOS environment during child-process startup; corrected it by capping each resource independently and ignoring only OS-rejected limit types. The full lifecycle suite then passed 8/8 in 0.674 seconds, including release/recovery verification. No branch merge or deletion was implemented.

Completed recovery-branch controls. A clean released task branch can be previewed with `git merge-tree --write-tree`; conflicts are returned without modifying the target. A merge requires a separate critical approval bound to the source and target commit IDs, preventing approval reuse if reviewed Git state changes. A merged branch can be deleted only after another critical approval bound to its commit ID and an ancestry check. Added a conflict-preview unit test and extended the opt-in HTTP lifecycle test through merge and branch deletion.

Verified the completed merge lifecycle: default tests passed 8 unit tests with the listener test intentionally skipped; with `PERSONAL_CODEX_HTTP_TESTS=1`, all 9 tests passed. The HTTP lifecycle also asserts that a target-branch commit after approval makes the old merge approval unusable, requiring a new review and approval.

Added provider-adapter metadata validation. The control plane now accepts only Ollama/OpenAI-compatible descriptors with absolute HTTP(S) endpoints; non-cloud descriptors must point at loopback and cloud consent is a strict boolean. `secret_ref` accepts only an environment-variable name. Registration and capability discovery never read a secret or contact the endpoint. Default tests passed 10 tests with the listener skipped; the opt-in HTTP suite passed all 11 tests and verifies the provider guardrails.

Applied the permanent cross-account continuation protocol. The stored next-session prompt is now regenerated at meaningful verified milestones, user-requested handoffs, and before usage exhaustion, and embeds the dedicated recursive protocol that every future account must preserve.

Configured the official GitHub `origin` and verified with `git ls-remote --heads` that it had no branch heads before first publication. Added permanent GitHub continuity, safe-push, and remote-verification requirements to the handoff checkpoints.

Published the complete verified local history to the empty GitHub `origin/main` without force-pushing, then verified the remote head at `2526fb4`.

Added an injected provider transport seam. It validates response shape, sends no secret-reference metadata to the transport, and creates a canonical approval description bound to provider, model, cloud flag, task, and prompt SHA-256. The default test suite passed 11 unit tests with the listener test skipped.

Wired the transport seam into the control plane as an approval-gated invocation lifecycle. `POST /api/tasks/{id}/provider-request` records a pending approval whose canonical detail binds task, provider ID, endpoint, model, prompt SHA-256, and cloud flag; `POST /api/tasks/{id}/invoke` refuses unless an approved record with that exact detail exists. Loopback providers require `provider-invoke` while a `cloud_allowed` provider requires a separate `network` approval, keeping stored metadata consent distinct from transmission consent. Responses are bounded and redacted, persisted in a new `invocations` table with the prompt digest (never the prompt), and exposed at `GET /api/tasks/{id}/invocations` plus an audit event. The shipped transport raises instead of opening a socket, so a v0 installation cannot transmit a prompt even with an approval.

Added browser-free dashboard contract tests in `tests/test_ui.py`: scripted element IDs must exist in markup, every markup button must have a handler, every `/api/` path used by `app.js` must be routed by `server.py`, the gated action controls (workspace, command, release, merge, branch delete, provider) must all be present, and the dashboard must load only local assets without browser-stored secrets. Also wired provider invocation controls and a provider-response ledger into the dashboard.

Verified: default suite 19 unit tests passed with the listener skipped; `PERSONAL_CODEX_HTTP_TESTS=1` suite passed all 20 tests including the provider lifecycle and cloud network-approval separation; `python3 -m py_compile app/server.py` and `node --check web/app.js` passed. A real loopback smoke test then confirmed health, the new dashboard controls, a 403 before approval, the bound approval detail, the fail-closed transport error with no invocation row written, and rejection of a cloud endpoint without consent; the server process was stopped afterwards.

Implemented real provider transports in `app/providers.py` (standard library only): Ollama `/api/chat` with `/api/generate` fallback, and OpenAI-compatible `/chat/completions`. `server.PROVIDER_TRANSPORT` now defaults to `None`, meaning the built-in adapters are selected per invocation through `active_provider_transport`; an injected callable still overrides them and `unavailable_provider_transport` still provides hard fail-closed behaviour. The request object carries kind, endpoint, model, prompt, and cloud flag but never the secret reference.

Hardening: `http.client` is used directly so proxy environment variables are ignored and redirects are never followed (3xx is an error); connections have a 60 s default timeout, responses are capped at 1 MB, JSON shape is validated, error text is whitespace-collapsed and capped at 240 characters, and the adapter repeats the loopback check unless the provider is cloud-consented. OpenAI-compatible credentials are read from the environment variable inside the transport closure at call time, used only in the Authorization header, and never returned or logged; a cloud provider without a secret reference and a missing credential both fail before any request is sent.

Added `tests/test_providers.py` with an ephemeral loopback stub server covering request shape/path, response extraction, malformed JSON, HTTP 500, redirect refusal, connection refusal, timeout, oversized response, unexpected structure, invalid endpoints, non-loopback refusal, credential handling, transport selection, and one opt-in API test proving an approved invocation reaches the built-in Ollama adapter and writes the ledger without any injection. Dashboard gained a provider transport-policy hint and a duplicate-invocation guard.

Verified: default suite 40 tests `OK (skipped=2)`; with `PERSONAL_CODEX_HTTP_TESTS=1` all 40 tests passed; `python3 -m py_compile app/server.py app/providers.py` and `node --check web/app.js` passed. No live model or external network was contacted.

Built the bounded agent tool layer in `app/tools.py` and wired it into the control plane. A provider now proposes JSON operations in a closed schema (`list_files`, `read_file`, `apply_patch`, `run_tests`); unknown tools, unknown or missing arguments, oversized values, absolute paths, `..`, ignored directories, secret-named files, and symlink escapes are rejected. `apply_patch` requires an exact single match and re-checks the reviewed SHA-256, so a file changed after approval fails instead of being overwritten. Execution stops at the first failure and marks the remaining operations skipped; `run_tests` delegates to the existing allowlisted executor through an injected runner.

Three endpoints implement the lifecycle: `/agent/request` builds a deterministic prompt (task, bounded workspace listing, tool schema) and queues an approval bound to its digest; `/agent/plan` rebuilds the same prompt, requires that approved invocation, validates and hash-binds the provider's proposal, stores it, and queues a second approval bound to the proposal digest and workspace; `/agent/execute` requires that approved digest, atomically claims the proposal to prevent duplicate execution, executes inside the task worktree, records per-tool events, and refuses if the stored proposal or workspace changed. Dashboard gained proposal, operation, and result panels plus request/build/execute controls.

Verified: default suite 56 tests `OK (skipped=4)`; with `PERSONAL_CODEX_HTTP_TESTS=1` all 56 tests passed, including proposal → approval → execution (file actually changed, tests run) and stale-file rejection (file preserved, run marked failed). `python3 -m py_compile app/server.py app/providers.py app/tools.py` and `node --check web/app.js` passed. README was rewritten to document the working workflow and its limits.


## 21 November 2026 — scoped Mac automation preview

Added a public-API native helper, private bounded stdio broker, reviewed local plans, selected-window Accessibility controls, optional capture/OCR, new browser window scoping and disposable native acceptance fixture. Stop invalidates scope without rolling back completed edits. Per-action safety is revalidated after earlier actions. 31 helper, 13 Rust and 17 frontend checks pass; optimized preview built. Installed local 9B initially chose an absent result attribute in an unrealistic fixture; fixture now mirrors the real labelled result value, validation rejects absent attributes, and a separate synthetic local-model trial passed. Actual UI test refuses without Accessibility; no real UI/browser/OCR success claimed. Preview remains separate from stable source and launcher. No server/network/policy changes or personal app inspection. Priority 1 is incomplete; later priorities are untouched.

The first hosted preview run passed backend tests but exposed undeclared Node file-system types in the new contract test. The contract test now uses Vite raw source imports with the declared Vite client types; no dependency was added and production application behavior is unchanged. Local tests/build were rerun and fresh hosted verification is required.


## 21 November 2026 — first real UI attempt and focus revision

The owner screenshot confirmed all three product permissions available. The first product synthetic self-check stopped with targetChanged; no actual action acceptance was claimed. Raising a window alone does not establish key focus. The driver now requests main/focused state on the exact bound window, waits for both the selected app and selected window, and retains its per-action target/focus guards. The fixture selects its primary key window and launches activated. The helper initializes AppKit. This is a proposed correction, pending actual rerun. Self-check failures now preserve stage, completed action count and bounded synthetic target metadata before terminating the owned fixture. No typed values or personal windows are logged. Apple references: https://developer.apple.com/documentation/appkit/nsrunningapplication/activate(options:) and installed AXAttributeConstants.h (AXMain does not imply key focus). No OS permission database, server or browser settings changed.

The first focus-revision headless check aborted because AppKit was initialized before selecting the in-memory self-test path. AppKit initialization is now restricted to permission-checked native paths; all 31 helper checks pass again. No owner OS grant was changed. The actual focus correction still awaits product rerun.


## 21 November 2026 — scrollbar diagnosis, window identity and the suite segfault

Environment: Linux cloud workspace. No macOS SDK, no Swift or cargo toolchain, no route to JARVIS
(100.117.60.12 timed out; no SSH identity present). Nothing was built, signed, installed or run on
the Mac, and no permission, TCC, server or family-service change was made. The installed
permission-approved preview was not touched because it is not reachable from here.

Diagnosed `native_scrollbar_result` from source: the fixture's `NSScrollView` kept the default
overlay scroller style, which hides the scroller until the user scrolls, so an `AXChildren` walk
cannot observe an `AXScrollBar`; the check failed before attempting a scroll. Fix: the fixture uses
`.legacy` scrollers, and the reader also walks the `AXVerticalScrollBar`/`AXHorizontalScrollBar`
relationships of `AXScrollArea` nodes under the existing bounds and inside the bound window.

Window identity: `begin` now carries the listed window title, the driver refuses a shifted index
with `targetChanged`, and the panel re-lists and compares titles before scoping.

Suite crash: intermittent SIGSEGV (exit 139, roughly one in eight verbose runs) reproduced under
`faulthandler` as a streamed-response thread inside `Store.rows()` while a teardown closed the
shared connection. `Store.close()` now closes under the store's RLock, teardowns use it, and
`test_close_waits_for_a_query_that_is_still_running` asserts the blocking behaviour.

Verified here: backend 378 tests OK (skipped=55), three consecutive verbose runs clean on the
previously crashing path; desktop `tsc -b` clean; 18 frontend checks pass. The skip count differs
from the historical 5 because loopback HTTP, the pinned gateway package and the disposable syscall
test are gated in this environment; they are consent/environment gates, not new failures.

Not verified: Swift compilation, native rerun, capture/OCR, browser workflow, and JARVIS access.
Priority 1 remains incomplete.

## 21 November 2026 — automation boundary, tested window identity, deterministic scrollbar

Continued priority 1 from a Linux workspace (no macOS SDK, no cargo, no JARVIS route). Publishing
remained blocked: the push tool transmits the primary checkout's HEAD, and switching that checkout
to this branch would overwrite the owner's uncommitted `web/style.css`. No force-push attempted.

Added `AutomationBoundaryTests`: the broker's operation allowlist is read from the Rust source, the
HTTP route table is rejected if any automation-shaped path appears, and no Python module may drive
the helper or speak its protocol. The guard was proven non-vacuous by injecting an
`/api/automation/execute` route, observing the failure, and restoring the tree.

Extracted the pre-scope window check into `automationWindow.ts` with unit tests (replaced window,
closed window, reordered list, untitled window refused as unidentifiable, no title leaking in
messages). Extended the binding to `AXWindowNumber`: the list reports it, the panel sends title and
number, and the driver refuses a mismatch, degrading to the title check when unavailable.

Found a defect created by the previous session's relationship traversal: a scroll area can expose
both bars, and the acceptance check took whichever came first, so an immovable horizontal bar could
make a working scroll look broken. It now prefers the vertical bar and records why no bar was usable.

Verified on Linux: backend 382 tests OK (skipped=55); backend with `PERSONAL_CODEX_HTTP_TESTS=1`
378 tests OK (skipped=4) before the boundary tests were added; frontend 26 tests pass; `tsc -b` clean;
`npm run build` (tsc + vite) clean. Not verified: any Swift compilation, every native rerun, capture
and OCR, the browser workflow, and the local-model end-to-end path.

## 21 November 2026 — phase 0 closed, publication unblocked, risk register

Started from the reported state and verified it instead of trusting it: the worktree was clean at
`bbcc62e`, 11 commits ahead of `origin/personal-codex/mac-automation`, and the primary checkout still
held the owner's uncommitted `web/style.css` untouched.

Diagnosed the publication failure rather than repeating it. The push tool transmits the chat
checkout's HEAD, which sits on the stable branch 32 commits behind its remote, so every earlier push
was rejected as "behind its remote counterpart". Re-pointing only that HEAD with
`git symbolic-ref refs/heads/personal-codex/mac-automation` for the duration of the push sent
`a6090d7..bbcc62e` as a fast-forward and then restored the branch. No file, index entry or branch
content changed: `git status --porcelain` and the `sha256sum` of `web/style.css` were identical
before and after, and `git ls-remote` confirms the new tip. No force-push, reset or checkout of user
work was performed. A verified bundle of the branch was also written to the chat workspace as a
second copy (`git bundle verify`: complete history).

Baseline re-run rather than quoted: 382 backend tests OK with 62 environment-gated skips, and 382 OK
with `PERSONAL_CODEX_HTTP_TESTS=1` (11 skips). The skip difference is the loopback HTTP, pinned
gateway wheel, disposable-syscall and macOS gates, not new failures.

Phase 1 review then found one real weakness that did not need a Mac. The synthetic self-check passed
`approval_is_one_use` on *any* thrown error, so an unrelated fault during the second execute would
have been reported as proven one-use enforcement. It now requires `AutomationError.actionNotConfirmed`
and records a failure otherwise. The stronger identity was also never exercised: the check bound a
wrong title only, so a wrong `AXWindowNumber` was implemented but untested. It now binds the correct
title with `number + 1` and records `window_number_identity_refused` when the fixture exposes a
number. A frontend contract test asserts both source shapes so a later edit cannot quietly undo them.
Frontend: 34 tests pass, `tsc -b` clean.

Wrote `docs/RISK_REGISTER.md`: 17 risks with severity, evidence, mitigation, verification method and
status. Phase 0 is recorded as passed, phase 1 as blocked on native acceptance, phases 2-5 as gated
and not started. Nothing in it claims a compiled or natively accepted result.

Not verified: any Swift compilation of `a6090d7..54a11bd`, the 31 helper self-tests, and every native
self-check. No compiler or macOS SDK exists in this workspace, and the hosted CI result is not
observable from here.

## 22 November 2026 — Phase 1 hardening and shared-foundation defects

This session again had no macOS host: `uname` is `Linux freestyle-vm 6.1.102 x86_64`, `swiftc`,
`xcrun`, `clang`, `cargo` and `codesign` are absent, there is no `/Users` or `/Applications`. No
native check was run and none is claimed. Every native change was compiled and self-tested by the
hosted `native` job instead, which is compile and in-memory evidence only.

Seven defects were fixed, each with a negative control run against the previous code:

- `5616276` — approval replay. Four guarded routes read `status='approved'` and never spent it, so one
  owner approval authorized unlimited provider invocations (including cloud) and unlimited runs of
  the same approved command. `Store.consume_approval` makes the spend an atomic
  `approved → consumed` transition. The HTTP lifecycle test returns **200** on the old code, **403**
  on the fixed code; a four-thread test proves exactly one caller wins.
- `c00e35a` — capture returned OCR text unscreened, although field values were already screened with
  the same predicate, and the protected fixture window was bound by a launch-time index that focus
  changes reorder. Capture now refuses credential-shaped OCR text with `unsafeTarget`, and the
  secure-window checks re-resolve the window by title. Run #26 compiled and self-tested this.
- `65a9493` — the acceptance summariser documented exit 4 for "helper could not run" but never
  returned it (missing helper exited 1, a hang escaped as a traceback), and a passing run said
  nothing about capture, OCR or the browser. Exit 4 now means exactly that, `verified` requires
  `actual_ui_exercised: true`, no report is saved for a run that did not happen, and a pass prints
  `NOT EXERCISED` for capture and the browser workflow.
- `26339e7` — the browser-origin refusals (cross-origin link press, cross-origin typed URL, a scope
  with no origin) were enforced in policy but only described by source-string contracts. They now
  execute in the macOS `native` job (run #30 passed).
- `586a3d3` — a restored recovery tree left `data/projects` and `data/workspaces` at 0755 while every
  other path was 0700/0600, because `Path.mkdir(parents=True, mode=0o700)` modes only the last
  component. Restored directories are created explicitly at 0700; the test fails on the old code.
- `80b4b70` — the display filter ran on the model's response before parsing, so a proposal containing
  `token=...` was rewritten to `token=[REDACTED]` and its JSON was usually rejected outright; stored
  output also kept `Authorization: Bearer ...` and bare `sk-` keys. Redaction now applies to
  stored/displayed text only, and covers those shapes.
- `7c6c6bc` — a chat turn marked its message `streaming` before its `try`, so a transient storage
  failure escaped `_run_turn`, left the message queued and kept its generation slot; the conversation
  then refused every later turn until restart. The `finally` now releases the slot and marks any
  still-active message `error`.

Verification actually run: `python3 -m unittest discover -s tests` with
`PERSONAL_CODEX_HTTP_TESTS=1` → 399 tests, OK, 1 skip after installing the optional `cryptography`
wheel locally to run the 10 recovery tests; `npx vitest run` → 38 tests; `npm run typecheck` clean;
each new regression test also run against the pre-fix code and observed to fail. Hosted CI: run #26
(`45045013891`, `c00e35a`) and run #30 (`45045487455`, `26339e7`) completed successfully, including
the macOS `native` job.

`docs/RISK_REGISTER.md` gains R-18 (approval replay, verified resolved), R-19 (restore-tree modes,
verified resolved), R-20 (output redaction, verified resolved) and R-21 (chat turn slot, verified
resolved); R-02 now records compile evidence through `c00e35a`, R-05 and R-06 record the new refusals
and their remaining native gap, and R-09 records the summariser corrections. Phase 1 stays
**partially verified**: every real-UI check in `docs/MAC_ACCEPTANCE_RUNBOOK.md` is still unrun.

## 22 November 2026 (continued) — eight more defects in the shared foundations

Same environment, same rule: no macOS host, so nothing native is claimed. Eight further defects were
fixed in the same loop, each proven by a check that fails on the previous code.

- `a40cb34` — completion evidence skipped rounds whose status was `failed`, so a round that ran work
  and broke it was invisible and an older passing round stood in as the latest evidence: the model's
  completion claim was accepted after the workspace had been broken.
- `28b500d` — `project_agent._run` prepared state before its own `try/finally`; an unexpected failure
  there left the single-run slot claimed and the row `running`, refusing every later coding run until
  restart. A supervisor now releases the slot and closes the row.
- `294f4e6` — the panel's self-check summary special-cased three statuses and rendered any other one
  with passing checks (`cancelled`, a future terminal state) as "All N checks passed."
- `eade3dc` — the approvals table had **no lifetime**: an approval stayed spendable forever. Approving
  now records a 600 s expiry, `consume_approval` refuses and marks a lapsed row, existing databases
  are backfilled, and the eleven positional approval inserts name their columns (a seventh column
  would otherwise have broken every approval creation).
- `0e35cb3` — six guarded setup routes (`workspace`, `release`, `apply`) read `status='approved'`
  directly, so an approval of any age authorized them, and an old row could shadow a fresh one. They
  now share `approval_permits`.
- `f26ae74` — the context walker promised to skip secret-named paths but selected `secrets.json`,
  `credentials.yaml`, `deploy.pem` and `id_dsa` into the model prompt, and ranked them higher when the
  task mentioned secrets.
- `5404c97` — `regenerate` rebuilt the prompt with the answer being replaced still in it, ending at
  `ASSISTANT: <old answer>` plus a final `ASSISTANT:` cue: a continuation request, not a new answer.
- `f8c7303` — `do_GET`/`do_POST` mapped only `ValueError`, `OSError` and SQLite errors and `do_DELETE`
  had no guard, so a `KeyError`/`TypeError` reset the connection and the panel could only say
  "Backend returned an invalid response".

Verification: 413 backend tests with `PERSONAL_CODEX_HTTP_TESTS=1` (1 skip: the recovery tier needs
the optional `cryptography` wheel), 39 frontend tests, `tsc -b` clean. Every new test was also run
against the pre-fix source and observed to fail there (recorded in each commit and in R-22…R-27).
The newly added tests were run fifteen times in a loop with no failure, because hosted run #45 for
`294f4e6` reported `failed` while its jobs passed at `f26ae74`; the failing job name was not
retrievable from this IP, so it is recorded as unexplained rather than as a passing check.
Hosted CI: run #50 (`45048266342`) for `f26ae74` **completed successfully** (backend, frontend,
macOS `native`).

A restart drill (`tests/test_restart_drill.py`, `d1f3e02`) then closed the ninth defect of the
session: the proposal-execution route claims a proposal without a round id, so a restart during that
path left the row `executing` for good — never reviewable, never runnable again, and shown as running.
`recover_interrupted` now closes every `executing` proposal, and the drill asserts the general
invariant: no table may keep `running`/`executing`/`streaming`/`queued` after a restart, while partial
messages, events and saved deliveries survive it. Final counts: 415 backend tests (1 skip), 39 frontend
tests, typecheck clean. The approvals panel now states the one-action, ten-minute lifetime that
`eade3dc` introduced.

The tenth fix of the session was on the display side: the panel summariser accepted any
`status: passed` report as "All N checks passed" even when the report never claimed a real UI run,
and it never named the workflows a run skipped. It now requires `actual_ui_exercised`, reports
`verified` only for a real run with passing checks, and lists the unexercised capture/OCR and
browser workflows (R-29, `54cbdad`). Frontend suite: 41 tests, typecheck clean. An audit of
`tools.py`, `providers.py`, `full_task.py`, `secure_files.py`, `native_projects.py` and
`scripts/mac_acceptance.py` found no further defect worth a change; the two CI runs at `294f4e6`
(#44, #45) reported failure with no retrievable job detail from this host, the same jobs passed at
`f26ae74`, and it is recorded as unexplained rather than resolved.

## Final verification (end of the second session)

Backend `PERSONAL_CODEX_HTTP_TESTS=1`: **415 tests, OK, 1 skip** (the skip is the optional
`cryptography` recovery tier, installed locally). Frontend: **41 tests in 8 files**. `npm run
typecheck` (`tsc -b`) clean. The six newest test modules were run ten times back to back with **0
failures**, so the added cases are not order- or timing-dependent in this environment.

The primary checkout was re-verified after `git status` briefly showed 193 staged deletions while
`HEAD` was re-pointed for a push: it is a linked worktree, its index has zero staged changes, its only
worktree change is the owner's `web/style.css` edit (sha256 unchanged from the start of the session),
all preserved untracked paths are present, no stash exists, and `HEAD` is back on
`personal-codex/stabilization` at `12a24d5`. The deletions were an artifact of comparing the newer
feature tree against the old stabilization index with a read-only command; nothing was staged,
deleted or repaired.

Hosted CI was last read green at `f26ae74` (run #50). Runs #44 and #45 failed with no retrievable
failing job from this host, and the runs for the last three commits were not yet listed; that is
recorded as unverified rather than green.


## 24 November 2026 — Codex integration baseline and cancellation boundary

Resumed in a separate macOS worktree at f6224e2, with green hosted baseline. Mac baseline: 422 backend tests, five named platform/optional skips; 41 frontend tests/build; 42 helper checks; 13 Rust tests, one optional model test ignored. No approved preview replacement. Reproduced legacy proposal mutations after cancellation using three disposable HTTP negative controls, then corrected per-operation stop propagation and cancelled terminal state. All six focused tests pass. The first draft reproduction expected cancellation HTTP200 instead of the existing202; that fixture assertion was corrected before collecting all three negative controls. Added integration-branch CI trigger and Codex coordination record. No new Freebuff batch is published on its assigned branch yet.

24 November: aligned direct workspace tools with context credential exclusions through a shared filename policy. Negative controls showed direct reads/listing/patches bypassing context exclusions. Five new tool policy checks plus context/containment checks pass. The positive control uses ordinary secret_parser.py; its first draft asserted the wrong read response key (content instead of existing text), corrected before collecting the negative control. No actual secret or protected diagnostic was read.

24 November: process-group stop no longer assumes a terminated parent means all descendants stopped. A child ignoring SIGTERM reproduced continued file writes after cancellation; cleanup now checks the entire owned group for a bounded grace period before SIGKILL. Focused group/cancellation checks pass (six cases, one /proc skip). No persistent owner processes or system settings changed.

## 24 November 2026 · Codex takeover, Session 1

Integrated Freebuff `4e27eb2` into Codex `c23411b` in merge `a98ec00`. The integration
branch now builds an isolated offline candidate, creates reviewed tasks directly from projects,
shows scoped approvals and operation progress, delivers via exact Git merge, surfaces project
memory, keeps archive search stable and regenerates the latest answer with the selected model.

A cloud browser drove a disposable calculator through failure, repair, review, release and merge.
The destination test passed independently. Task status, delivery and exit codes survived a backend
restart. Proposal and chat inference were scripted. The Mac CI job compiled Rust and the helper,
ran its policy tests, exercised scripted full-task delivery and built the candidate app. See
[the integration record](docs/AGENT_COORDINATION_CODEX.md) for exact runs and
[the Session 2 prompt](NEXT_SESSION_PROMPT.md) for the remaining M3 and live-model gates.

## 27 November 2026 · Final owner-test candidate

Started from `dae8901` and independently verified the published ARM64 artifact and green run #118.
This Linux workspace had no Ollama executable or reachable loopback Ollama. The live fixture refused
before creating its output directory. Interactive candidate acceptance requires the owner's Mac.
Managed offline launches now restrict the picker and provider policy to supported models present at
startup. Live fixture runs can choose either supported model and check discovery before setup.

Readiness now follows the task worktree and can be refreshed after operator setup. The desktop
exposes the exact directory and declared start command for a dedicated terminal. Installation and
dev-server processes stay operator-managed because the contained runner denies network and limits
writes to named output directories. The CI artifact contains a checksum for the app archive.

The owner reports JARVIS online. The existing private HTTPS, outbound worker, isolated service,
capacity and rollback plan was reviewed locally. No authorized JARVIS connection was available
here. Target checks and deployment remain pending separate owner action. [Owner guide](docs/FINAL_TESTING_GUIDE.md)

## 28 November 2026 · Completion inventory and supervised review

Verified the previous release and recorded the outstanding capability and acceptance gates. Fixed the
desktop dead end after a proposal is rejected, stale or expired by adding an exact discard action.
Discard preserves the worktree and revokes the proposal approval. A cancelled supervised task can
request a fresh plan with a new approval. The execute button binds the action to the displayed
proposal, and the server consumes that approval with the claim. Added saved-note corrections and
selection of supported declared npm checks into the existing command review.

This workspace lacked real Ollama, interactive macOS and authorized JARVIS access. Network-enabled
install and server lifecycle remain operator-managed. [Product inventory](docs/PRODUCT_COMPLETION.md)

The follow-up check exposed a race in local task recovery. The supervisor cleared the active slot
before persisting terminal status. The supervisor now saves a failed state for the run and any
running task before releasing the slot, including failures that happen before normal execution
cleanup. The desktop also shows planning context file ranges without displaying raw prompts.

Mac CI run #123 stopped during the offline backend startup smoke test before bundling. The
HTTP listener no longer performs a reverse DNS lookup while binding. The launcher now keeps
immediate backend logs and reports the last readiness error after a bounded 30-second window.
The synthetic launcher and actual Mac acceptance remain distinct checks.

## 28 November 2026 — Mac repair sprint

Started from published integration 0a8d742 in the clean integration worktree. Two synthetic negative controls reproduced readiness reading a hardlinked manifest and a manifest swapped to a symlink between metadata and read. Reused descriptor-relative no-follow reads with a bounded manifest byte limit and link/change checks. Focused suite: 24 discovered, 21 passed, three HTTP-gated skips in the restricted invocation. Current published main, approved preview, profiles and protected diagnostic remain untouched. Broader HTTP/native/live-model checks are recorded after completion.

Reviewed dependency installation now creates an exact expiring proposal for npm lockfile v2/v3 packages from registry.npmjs.org. Explicit install and network confirmations are required. Downloads are fixed-origin TLS, nonredirecting, byte-bounded and SHA512-verified; archive links/traversal are refused. npm runs offline with lifecycle scripts disabled inside the Mac process boundary, using a private staging/cache. Only a new node_modules is published after manifest and directory revalidation; existing dependencies are never replaced. Cancellation and startup interruption never replay installation. Source/lockfile bytes remain unchanged. Twelve focused backend checks passed, including real contained npm plus HTTP owner/confirmation checks. Frontend 98 tests and production build passed. An explicit public is-number@7.0.0 acceptance download/install passed in a new disposable profile. No JARVIS access. Broader package managers, lifecycle scripts, workspaces and replacement installs remain unsupported.

Actual installed qwen3.5:9b existing-project calculator repair passed: three inference calls, 49.23 seconds, real contained verification and delivered files. Baseline after the descriptor fix: 473 discovered, 468 passed, five platform/optional skips. Helper: 42 in-memory checks; Rust: 13 passed and one installed-model case ignored. The isolated helper reports Accessibility/key events unavailable, screen capture available. Native click/type acceptance remains pending; no permission changes or approved-preview replacement occurred.

Managed Node previews now bind one inherited app-owned loopback listener, with new binds/outbound connections denied. The rejected first profile used a localhost bind exception; a negative control showed wildcard binds could briefly succeed. Explicit new-bind denial plus inherited listener/bootstrap passed raw child bind/connect denial, wildcard confinement, read-only project, readiness/logs/stop, unrelated-port preservation and hard-killed-backend cleanup. Ten preview checks pass; combined managed lifecycle: 22 checks. Full backend: 495 discovered / 490 passed / five skips. Frontend: 101 checks, production build; Rust 14 passed / one optional model ignored. Isolated ARM64 app built and ad-hoc signed; no approved preview replacement. UI owner acceptance and broader framework adapters remain open. Current native workflow also runs the managed process tests.

Hosted d004674 native CI caught npm module reads denied for setup-node's tool-cache path. The shared runner now permits only the selected executable and the selected npm package tree, with synthetic tests proving sibling data remains denied. No broad tool-cache/home read grant was added. Launcher reuse of an existing loopback Ollama is now explicit (--reuse-ollama); it never starts/stops/reconfigures that daemon and retains backend-port conflict checks.

The real 9B web implementation exposed structured replies repeatedly ending at 768 output tokens and failing JSON parsing. Four new regressions failed on the old code: code/chat budget distinction, streaming/nonstream truncation reporting, and nonstream round JSON mode. Structured offline replies now have a bounded 2048-token budget (chat remains 768), report length termination as a token-limit error, and keep JSON mode in nonstream rounds. Full-task prompts request small complete file changes. Failed synthetic web evidence is preserved; repeat acceptance is recorded separately.

## 28 November — interrupted sprint resumed

Resumed the exact dirty d004674 worktree; no reset or discarded changes. Four structured-output regressions and focused provider/launcher/toolchain checks passed, and the completed changes were published as 6b919b5. CI #127's failure was traced to setup-node npm module reads; the selected npm package tree is now the only additional tool-distribution read scope. Prior full Mac suite: 503 discovered, 498 passed, five skips.

The preserved real web repeat progressed beyond truncated JSON, but its model plan incorrectly chose a long-running declared Node server as a contained CLI smoke test. This caused DNS/bind failures and misguided repair attempts against protected independent tests. A negative planning regression reproduced the unsupported smoke selection. Planning now explicitly separates HTTP preview acceptance from finite CLI smoke checks, rejects a declared Node development entry as a smoke command, and retains ordinary CLI smoke support and independent tests. The original failed profiles/receipts remain intact.

The next preserved 9B web attempt generated complete file proposals but relocated explicitly requested calc.js/server.js to src/. The basename resolver then treated the planned nested names as authoritative, while independent tests and the declared dev command expected the root paths. The model attempted to change validation files and was correctly refused; loop detection stopped the repeat. A negative parser regression reproduced the relocation. Explicit create/write/add root-path requests now require that exact plan path, while diagnostic basename resolution remains supported. Terminal startup instructions for a declared web server also no longer force an inappropriate CLI smoke. New planning regressions pass; no validation guard was weakened.

Actual isolated GUI startup authenticated successfully. Settings navigation and the Mac opening panel were visually inspected; installed-app search and preparation/cancellation of a Calculator opening review worked without launching that app. The candidate reports Accessibility and keyboard-event permissions unavailable, screen capture available; grants and the approved preview were preserved.
