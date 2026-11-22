# Personal Codex: current continuation

Updated 22 November 2026. Continue the same active mission on `personal-codex/mac-automation`.
Stable source `64189ef30177922481d17da242d11a90baf3c599` (`main` and
`personal-codex/stabilization`) is untouched and must stay that way until acceptance justifies more.
Draft PR #2 stays a draft and is not to be merged. The feature head is this document's commit; its
parent is `f8c7303`. Confirm with `git log --oneline -5` and `git ls-remote origin`.

## Read first

README.md, PROJECT_STATUS.md, docs/MAC_AUTOMATION.md, docs/IMPLEMENTATION_MATRIX.md,
docs/RISK_REGISTER.md, docs/MAC_ACCEPTANCE_RUNBOOK.md, SECURITY.md and current Git status/log.
Preserve all prior source, profiles, bundles, task worktrees and local model caches. Never read,
stage, modify or archive the protected untracked `personal-codex-diagnostic.txt`. Keep private
deployment/permission receipts in the chat workspace, not in public Git.

## Environment reality (verified again this session)

There is still no macOS host here: `uname` is `Linux freestyle-vm 6.1.102 x86_64`, `swiftc`, `xcrun`,
`clang`, `cargo` and `codesign` are absent, and there is no `/Users` or `/Applications`. **No native
check has been run, and none may be claimed.** The hosted macOS `native` job is the only native
evidence available: it compiles the helper and runs its in-memory self-tests and the 13 Rust tests.
That is compile plus policy evidence, not windowed UI acceptance.

Hosted verification is readable at the run pages (the GitHub API is rate-limited from this IP):
run #26 (`45045013891`, `c00e35a`), run #30 (`45045487455`, `26339e7`) and run #50 (`45048266342`,
`f26ae74`) **completed successfully** — backend, frontend, and the macOS `native` job. Run #45 for
`294f4e6` reported `failed`; its failing job was not retrievable from here and the same jobs passed
at `f26ae74`, so treat it as unexplained rather than resolved. Every later commit needs its own run.

Publishing still works only through the documented workaround: `cloud_git push` sends the chat
checkout's HEAD, which sits on the stable branch. Re-point only that HEAD with `git symbolic-ref`,
push, restore it, then confirm `git status --porcelain` and the `sha256sum` of `web/style.css` are
unchanged. A verified bundle is in the chat workspace at `.safety/mac-automation.bundle`.

## What this session fixed (all verified, all with negative controls)

| Commit | Defect |
|---|---|
| `5616276` | One approval authorized unlimited provider invocations (including cloud) and command runs: four routes read `status='approved'` and never spent it. Now `Store.consume_approval` is an atomic `approved → consumed` spend; old code returned **200**, fixed code returns **403**. |
| `c00e35a` | Capture returned OCR text unscreened (credential-shaped text now refused with `unsafeTarget`); the protected fixture window was bound by a launch-time index that focus reorders and is now re-resolved by title. |
| `65a9493` | `scripts/mac_acceptance.py` documented exit 4 but never returned it; a pass could not say what it had not exercised. Exit 4 now means "helper never ran", `verified` requires `actual_ui_exercised: true`, no report is saved for a run that did not happen, and a pass prints `NOT EXERCISED` for capture and the browser workflow. |
| `26339e7` | The browser-origin refusals are now executed in the macOS `native` job, not merely asserted as source strings. |
| `586a3d3` | A restored recovery tree kept `data/projects` and `data/workspaces` at 0755; every restored directory is now created at 0700 and every file is 0600. |
| `80b4b70` | The display filter rewrote the model's proposal before parsing (`token=...` became `token=[REDACTED]`, JSON often invalid) while `Authorization: Bearer ...` and bare `sk-` keys survived in stored output. |
| `7c6c6bc` | A chat turn that failed before marking itself streaming leaked its generation slot and wedged the conversation until restart. |
| `a40cb34` | Completion evidence ignored rounds whose status was `failed`, so an older passing round stood in as the latest evidence and completion was accepted after the workspace had been broken. |
| `28b500d` | `project_agent._run` prepared state before its own `try/finally`; a failure there kept the single-run slot and the `running` row, refusing every later coding run until restart. |
| `294f4e6` | The panel read any unrecognised self-check status with passing checks as "All N checks passed." |
| `eade3dc` | Approvals had no lifetime: an approval stayed spendable forever. Approving records a 600 s expiry, a lapsed approval is refused and marked expired, existing rows are backfilled, and the approval inserts name their columns. |
| `0e35cb3` | Six setup routes (`workspace`, `release`, `apply`) accepted an approval of any age and let a stale row shadow a fresh one; they now share `approval_permits`. |
| `f26ae74` | The context walker selected `secrets.json`, `credentials.yaml`, `deploy.pem` and `id_dsa` into model prompts and search results. |
| `5404c97` | `regenerate` handed the model its own previous answer followed by an `ASSISTANT:` cue, so it could only continue the old text. |
| `f8c7303` | An unexpected handler error (`KeyError`/`TypeError`; `do_DELETE` had no guard) reset the connection instead of answering bounded JSON. |
| `54cbdad` | The panel's summariser called a passing self-check report with no real UI run a full pass and never named the workflows it skipped; it now requires `actual_ui_exercised`, exposes `verified` and lists what was not exercised. |
| `d1f3e02` | A proposal claimed by the proposal-execution route (no round id) stayed `executing` after a restart, so it could never be reviewed or run again. Found by a new restart drill that asserts no table keeps an in-flight status. |

Verification actually run at the end of the session: `python3 -m unittest discover -s tests` with
`PERSONAL_CODEX_HTTP_TESTS=1` → **415 tests, OK, 1 skip** (the optional `cryptography` wheel was
installed locally to run the 10 recovery tests; CI without it skips that tier);
`npx vitest run` → **41 tests**; `npm run typecheck` (`tsc -b`) clean. Each new regression test was
also run against the pre-fix source and observed to fail.

## Phase 1 status: partially verified, still blocked

Implemented and self-tested: reviewed `set_text`/`press`/`key`/AX `scroll`, one-use approvals with
expiry, stale-window and focus revalidation after every step, secure-control omission, selected-window
capture with protected-window refusal, origin-bound browser scopes, and local-model planning against
the synthetic window.

Not run on any Mac: every real-UI check in `docs/MAC_ACCEPTANCE_RUNBOOK.md` — the synthetic
self-check (scrollbar, both identity guards, one-use, stale, cancellation), capture/OCR with
protected-window refusal, the disposable new-window browser workflow with the cross-origin negative,
and the local-model plan against a real window. Phase 1 does not advance until those pass.

## Exact next work

1. On the M3, run `python3 scripts/build_mac_automation.py --self-test` and
   `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml -j 2`, then
   `python3 scripts/mac_acceptance.py --run --save mac-acceptance.json` and
   `--run --capture --save mac-acceptance-capture.json`. Grant Accessibility (and Screen Recording
   for capture) yourself; never edit TCC or grant Terminal as a parent workaround.
2. Continue runbook stages 4-7 and report the first failing `stage`/`error`/check name verbatim.
   A `NOT EXERCISED` line is not a pass.
3. Update `docs/RISK_REGISTER.md` (R-01, R-05, R-06, R-07, R-08, R-10) from the actual results only,
   and fix defects without weakening any check.
4. Only after Phase 1 is accepted: end-to-end integration (Phase 2), then data integrity and recovery
   drills (Phase 3), model/hardware reliability (Phase 4), autonomy acceptance (Phase 5), foundation
   readiness review (Phase 6), the opening-panel visual pass, then JARVIS read-only planning.

While native acceptance stays blocked, independent work in shared foundations is allowed and useful
(data-integrity tests, SQLite concurrency, crash recovery, approval and tool safety, task resumption,
observability) provided it does not claim Phase 1 acceptance or quietly broaden autonomy.

## Constraints that still hold

No force push, no hard reset, no history rewrite, no merge of PR #2 into `main`. Do not overwrite or
re-sign the permission-approved Automation Preview, modify TCC or auto-approve OS prompts. Do not use
personal applications or the user's browser tabs for acceptance. Do not start/stop the owner's Ollama
daemon or replace models. JARVIS deployment is not live: dashboard reachable, HTTPS/backend refused,
storage/image/import/identity/family-access gates unresolved. Do not ask for the unknown key
passphrase, extract or reset credentials, assume a Docker operator, or use sudo/group/socket/API
workarounds. Preserve family backup directories and existing family/emergency access, and obtain
explicit approval of exact target operations before changing deployment, network, Serve or policy
settings. Storage invariants: 200 decimal GB free reserve, 24 GB API data admission, 75 GB overall
maximum, 25 GB initial total; admission/DB caps are not a hard volume quota.

## Continuation protocol

After every meaningful verified milestone, refresh this file, `docs/RISK_REGISTER.md`,
`DEVELOPMENT_LOG.md`, `PROJECT_STATUS.md` and `SESSION_HANDOFF.md` from actual source, checks,
failures/skips and remaining approvals. Require the next session to do the same. Keep private
evidence outside Git, preserve the protected diagnostic and all uncommitted user changes, and never
describe partially verified work as complete.
