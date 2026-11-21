# Risk register

Last updated 21 November 2026 on `personal-codex/mac-automation`.

Statuses mean exactly this:

- **Open** — known, not mitigated.
- **In progress** — mitigation under way.
- **Implemented, unverified** — code and a Linux-side check exist; the required acceptance run has not happened.
- **Blocked** — cannot progress in the available environment; needs owner action.
- **Verified resolved** — a check that would fail on the old behaviour passes on the new code.
- **Accepted residual** — knowingly left, with the reason and its limit recorded.

Severity is judged on the impact of the risk being real, not on how likely it is. Nothing here is
"no risk": every accepted item states what remains unproven.

## Foundation gate summary

| Phase | Requirement | Gate state |
|---|---|---|
| 0 | Source preserved, commits published, rollback points, baseline green | **passed** |
| 1 | General Mac automation, natively accepted | **partially verified** — hosted CI compiles the Swift/Rust and passes the 31 helper self-tests and 13 Rust tests; real-UI acceptance still needs the owner's Mac |
| 2 | Full-system integration workflows | not started — gated behind phase 1 |
| 3 | Data integrity and recovery drills | partially covered by earlier work; full drill not started |
| 4 | Model and hardware reliability | not started — gated behind phase 1 |
| 5 | Autonomy and agent safety acceptance | not started — gated behind phase 1 |

Phase 1 is a mandatory acceptance gate and it is blocked, so phases 2–5 do not begin. Phase 0 work
(publishing, backups, baseline, this register) did not depend on macOS and is complete.

## Register

| ID | Severity | Component | Evidence | Mitigation | Verification method | Status | Remaining limitation |
|---|---|---|---|---|---|---|---|
| R-01 | High | Mac automation native acceptance | CI now proves the helper builds and its in-memory policy tests pass on macOS, but no permissioned UI session has run: `docs/MAC_ACCEPTANCE_RUNBOOK.md` lists every unrun check | `scripts/build_mac_automation.py --self-test` and `cargo test` on every push; the panel runs the synthetic UI self-check on demand | Owner-run runbook on the M3 (Accessibility granted by the owner), recording each named check | **Blocked** | Only a permissioned Mac session can close this. Compilation and policy tests do not substitute for it. |
| R-02 | High | Swift/Rust compile | Workflow run 44859571919 ("Verify Personal Codex" #19, commit `7366121`) reported **completed successfully**: backend, frontend, the macOS `native` helper build with `--self-test` (31 checks) and `cargo test --locked` (13 tests) | Every push compiles and self-tests on `macos-latest`; target `arm64/x86_64-apple-macos14.0`, `-swift-version 5` | The run page's overall conclusion; CI fails the whole run if any job fails | **Verified resolved** for `7366121` | Commits after `7366121` are compiled only by their own CI run. Read that run before claiming a compile result. |
| R-03 | High | SQLite connection lifecycle under streaming | Intermittent SIGSEGV (exit 139, ~1 in 8 verbose runs) reproduced with `faulthandler` as `Store.rows()` on a streamed response while a teardown closed the connection | `Store.close()` closes under the store `RLock`; all teardowns use it | `test_close_waits_for_a_query_that_is_still_running`; full suite repeatedly | **Verified resolved** (Linux) | Crash was timing-dependent; a different connection use could still race. Not re-measured under a Mac load profile. |
| R-04 | High | Unpublished commits / no remote copy | 11 commits existed only in this workspace's bare repository | Fast-forward push `a6090d7..bbcc62e`, plus a verified bundle at `.safety/mac-automation.bundle` in the chat workspace | `git ls-remote origin personal-codex/mac-automation`; `git bundle verify` | **Verified resolved** | Remote copies are only as good as the next push; the bundle lives with the workspace checkpoint. |
| R-05 | High | Selected-window capture and OCR | `capture()` implemented; protected-window refusal path implemented; never executed | Capture requires separate consent, permission, a unique window match by title and frame, unchanged post-capture digest, and refuses a truncated or sensitive observation | Panel self-check with "also check capture" (needs Screen Recording) | **Implemented, unverified** | Screen Recording permission and a Mac session are required. |
| R-06 | High | Browser workflow (new window, origin, focus, existing tabs) | `Browser.swift` creates and focuses a new window; the self-check reports `browser_exercised: false` | New window is observed before the address is entered; the driver now binds the created window by title/number instead of its index, which a new window can reorder; scope binds one origin; cross-origin transitions throw `targetChanged` | Owner-run disposable form in a newly created window, existing tabs untouched (runbook stage 7) | **Implemented, unverified** | No automated native check exists for this path; only source-level contract tests. Largest untested area, and the only one that touches a real browser. |
| R-07 | Medium | Scrollbar observation | Original failure: the fixture used macOS overlay scrollers, so the `AXChildren` walk never saw an `AXScrollBar` | Fixture forces `scrollerStyle = .legacy`; reader walks `AXVerticalScrollBar`/`AXHorizontalScrollBar` relationships; the check prefers `.scrollV` deterministically and records a reason when no bar is usable | Panel self-check check `native_scrollbar_result` | **Implemented, unverified** | Real apps may still expose bars only through other relationships. |
| R-08 | Medium | Window identity binding | A window index is only a position; title alone can be edited or duplicated | `begin` carries the listed title and `AXWindowNumber`; the driver refuses a mismatch; untitled windows are refused as unidentifiable | Self-check `window_identity_refused` and `window_number_identity_refused` | **Implemented, unverified** | The number check only runs when the app exposes `AXWindowNumber`; otherwise title-only applies. |
| R-09 | Medium | Self-check assertion quality | `approval_is_one_use` recorded a pass for *any* thrown error, so an unrelated fault could look like proven one-use enforcement | The check now requires `AutomationError.actionNotConfirmed` and records a failure for anything else; a frontend contract test asserts the source shape | `npx vitest run` (contract test) + the native self-check | **Implemented, unverified** | Any native assertion is only as strong as its run; this one has not run natively. |
| R-10 | Medium | Local-model plan against a real window | A 9B proposal passed the helper policy and the in-memory synthetic driver only | Planning stays local (existing Ollama, no download/cloud), text consent required, every proposal reviewed and executed once | Panel: suggest a plan for the synthetic fixture, then approve it | **Implemented, unverified** | Model output quality on the real AX tree is unmeasured. |
| R-11 | Medium | Environment-gated skips | Default suite: 382 tests, 62 skipped. HTTP tier: 382 tests, 11 skipped. Gates are loopback HTTP, the pinned `respan-gateway` wheel, disposable-syscall support and macOS | Gates are explicit env switches, not silent passes; skipped tests are named | `python3 -m unittest discover -s tests` and with `PERSONAL_CODEX_HTTP_TESTS=1` | **Accepted residual** | 11 tests need a macOS host; their native subjects are covered by R-01/R-02. |
| R-12 | High | JARVIS / ThinkPad integration | `100.117.60.12` times out; no `~/.ssh`; no read-only access from this environment | No changes attempted; deployment stays read-only until an exact plan, impact analysis, rollback and owner approval exist | Owner-run read-only probe | **Blocked** | Outside the foundation gate; explicitly deferred by priority. |
| R-13 | Medium | Opening-panel visual acceptance | Not performed | Deferred by the standing priority order | Owner-led visual pass | **Open** | Must not be claimed as accepted. |
| R-14 | Medium | Model performance on the target MacBook Air M3 (16 GB) / ThinkPad T470 | No measurements on target hardware | Phase 4 work, gated behind phase 1 | Benchmarks on the real machines | **Open** | No claim about viable model size or latency is justified yet. |
| R-15 | Medium | Agent autonomy lifecycle (plan → edit → test → deliver) | Not exercised end to end in this phase | Phase 5 work, gated behind phase 1 | Disposable coding project with real outputs | **Open** | No broadening of autonomy before phase 1 acceptance. |
| R-16 | Low | Publishing mechanism | `cloud_git push` sends the chat checkout's HEAD, which sits on the stable branch and is behind its remote; switching that checkout would discard the owner's uncommitted `web/style.css` | HEAD was re-pointed with `git symbolic-ref` for the push only, then restored; no file, index or branch content changed | `git status --porcelain` and `sha256sum` of `web/style.css` identical before and after; `git ls-remote` shows the new tip | **Verified resolved** | The workaround is needed for every push from this workspace until the checkout itself is on the feature branch. |
| R-17 | Low | Automation helper signing | `codesign --sign -` ad-hoc, not notarized; helper is `LSUIElement` | Build receipt records `signature: ad-hoc; not notarized` and `permissions_granted: False` | Build receipt | **Accepted residual** | macOS may re-prompt after rebuilds; no signing identity is changed here. |

## What the next session must not claim

- That any commit **after** `7366121` compiles; each needs its own green `native` job. `7366121` itself is compiled and self-tested by run 44859571919.
- That any native check passed, because none has run.
- That capture, OCR, browser isolation or the local-model path are accepted.
- That the Linux suite substituting for macOS proves native macOS behaviour.

## Minimum owner action to unblock phase 1

1. Read the macOS CI result for the pushed branch (the `native` job is the first compile).
2. On the Mac checkout, run `python3 scripts/build_mac_automation.py --self-test`, then
   `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml -j 2`.
3. Open the panel, grant Accessibility yourself, run the synthetic check, then the same check with
   capture enabled if Screen Recording is granted.
4. Report the exact failing stage or check name from the panel summary. Each failure names its
   stage, so the fix does not require guessing.

Nothing above needs a token, permission change or TCC edit from this session, and none was made.
