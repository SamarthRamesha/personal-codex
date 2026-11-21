# Personal Codex: current continuation

Updated 21 November 2026. Continue the same active mission on `personal-codex/mac-automation`. Preserve stable source `64189ef30177922481d17da242d11a90baf3c599` and the existing default launcher/profile. GitHub updates are authorized; this unaccepted feature must remain isolated from stable main.

## Read first

Read README.md, PROJECT_STATUS.md, docs/MAC_AUTOMATION.md, docs/IMPLEMENTATION_MATRIX.md, SECURITY.md and current Git status/log. Preserve all prior source, profiles, bundles, task worktrees and local model caches. Never read, stage, modify or archive the protected untracked personal-codex-diagnostic.txt. Private deployment/permission/check receipts belong in the chat workspace, not public Git.

## Latest session (21 November 2026)

Feature head is now **published**: `personal-codex/mac-automation` is at `54a11bd` on origin
(fast-forward `a6090d7..bbcc62e`, then `54a11bd`). Publishing had been failing because the push tool
sends the chat checkout's HEAD, which is the stable branch and behind its remote; re-pointing only
that HEAD with `git symbolic-ref`, pushing, and restoring it left every file byte-identical
(`web/style.css` hash and `git status` matched before and after). A verified bundle also sits in the
chat workspace at `.safety/mac-automation.bundle`.

Linux-verified this session: backend 382 tests OK with 62 environment-gated skips, and 382 OK with
`PERSONAL_CODEX_HTTP_TESTS=1` (11 skips); frontend 34 tests pass; `tsc -b` clean. Earlier sessions on
this branch added the automation-boundary tests (mutation-tested), unit-tested window identity,
`AXWindowNumber` binding, the deterministic scrollbar check, and the panel's self-check summary. This
session tightened `approval_is_one_use` so only `AutomationError.actionNotConfirmed` counts as proof
and added a native `window_number_identity_refused` check, and wrote `docs/RISK_REGISTER.md`.

Still unverified and requiring the Mac: every Swift compile, the 31 helper self-tests, the synthetic
self-check including the scrollbar and both identity guards, capture/OCR and protected-window refusal,
the new-window browser workflow, and the local-model plan against a real synthetic window. The macOS
CI job (`scripts/build_mac_automation.py --self-test` plus `cargo test`) compiles and self-tests the
helper on push, so read its result first and use its failure stage before touching the panel.

`docs/RISK_REGISTER.md` is the gate record: phase 0 passed, phase 1 is blocked on native acceptance,
and phases 2-5 do not start until it passes. Do not describe any of the above as accepted.

## Current first priority

Implement and accept general Mac automation before advancing to any later priority. The branch adds a Swift helper using public Accessibility/ScreenCaptureKit/Vision, a bounded private stdio Rust broker and a separate React panel. Supported actions are reviewed set_text/press/Enter/Tab/Escape/AX scrolling. Scope lasts ten minutes/32 actions; a proposal lasts two minutes and is consumed once. Recheck target/focus/permissions and action safety after every step; stop on stale or ambiguous state without retrying completed actions. Natural-language planning uses only existing local 9B/14B Ollama after text consent; no downloads or cloud fallback.

31 helper policy checks, 13 Rust checks and 34 frontend checks pass. An optimized separate preview builds. A local 9B proposal passed the actual helper policy and synthetic in-memory driver; earlier failure and correction are retained privately. These are not real UI acceptance. The owner has granted the product permissions. The first actual native self-check stopped with targetChanged. A focus-handling revision now requests exact-window focus and waits for both app/window focus; failure reports contain stages and synthetic metadata. Actual rerun is pending. Browser adapters, native click/type/scroll, selected-window OCR/capture and local-model-to-real-UI flows remain unaccepted.

The owner was asked to manually grant Accessibility to Personal Codex Automation Preview or its named embedded helper, then check permission in the panel. Never edit TCC or grant Terminal/Codex as a parent workaround. Only the owner can approve OS prompts. The disposable fixture contains synthetic data and expires after two minutes; the self-check terminates only the exact fixture it launched. Do not use personal apps for acceptance or touch the current browser window. A CUA connection previously hung despite its timeout; do not repeat that connection or use a removed tool namespace.

## Exact next work

1. Verify current preview source hashes/signature and permission status. If owner grants, run the bundled native synthetic self-check through the product, record actual results and fix observed issues. Keep optional capture separately consented. Do not count in-memory tests as UI acceptance.
2. Accept a disposable browser form in a newly created window, preserving existing tabs. Verify origin/focus isolation, stale-state refusal, Stop and meaningful changed results. Natural-language proposals still require exact review. Known app/label/credential filters are heuristic and public AX support varies; do not promise hostile-app isolation or universal automation.
3. Update readable docs, private receipts/checkpoints and the feature branch from actual tests; inspect current hosted CI. Do not merge the preview into stable main until acceptance is justified. No force push.
4. Only when priority 1 is complete: visually accept the earlier opening panel, then reassess JARVIS read-only and prepare exact deployment operations, then broader development workflows, then production operations.

JARVIS deployment is not live. Last prior read-only evidence: dashboard reachable; HTTPS/backend refused; storage/image/import/identity/family-access gates unresolved. No JARVIS changes occurred in this phase. Do not ask for the unknown key passphrase, extract/reset credentials, assume a Docker operator, use sudo/group/socket/API workarounds or revive either declined transient probe. Preserve all family backup directories and existing family/emergency access. Obtain explicit approval of exact target operations before modifying deployment/network/Serve/policy settings.

The existing local coding/chat/history/document/memory/cycle-guard behavior remains. The backend source is unchanged by this UI phase; prior exact API context passed 17 disposable-container checks and the latest earlier backend suite was 372 passed / 5 skipped. Those checks do not certify JARVIS, production coding isolation or general project generation. Do not start/stop an owner Ollama daemon or replace existing models.

Storage invariants: preserve 200 decimal GB free; 25 GB initial total including image/staging/log/recovery overhead, 24 GB API data admission, 75 GB overall maximum. Admission/DB caps are not a hard volume quota. Encrypted recovery's current 64 MiB envelope is not production-capacity recovery.

## Permanent cross-account continuation protocol

After every meaningful verified milestone and before context/usage exhaustion, refresh this file, status, handoff and development log from actual source, checks, failures/skips, current infrastructure facts and remaining approvals. Require the next account to do the same. Keep private deployment evidence outside Git, preserve the protected diagnostic and user changes, and do not claim partial work is complete. Git history retains previous detailed milestones; this concise current checkpoint supersedes stale historical status and paused sections.

If the owner asks to pause, safely stop only task-owned processes, save consistent state and wait for a subsequent user message saying “it's back”. The prior pauses have already been fulfilled and do not block this active mission.
