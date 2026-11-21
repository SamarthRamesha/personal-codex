# Mac acceptance runbook (owner-run, MacBook Air M3)

This closes the only remaining Phase 1 gate. Everything here runs on your Mac against **synthetic
fixtures only**; nothing in it reads a personal app, personal window, real credential or existing
browser tab. Do the stages in order and stop at the first failure — each failure names its stage or
check, so no guessing is needed.

## What is already verified, and by what

| Claim | Evidence |
|---|---|
| The helper and fixture compile | GitHub workflow "Verify Personal Codex" #19 at `7366121`: `native` job ran `scripts/build_mac_automation.py --self-test` |
| 31 in-memory policy/session self-tests | Same job, `--self-test` (no permissions, no window) |
| 13 Rust broker tests | Same job, `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml -j 2` |
| 35 frontend tests, typecheck | `frontend` job; and locally `npx vitest run`, `tsc -b` |
| Backend + HTTP regression | `backend` job with `PERSONAL_CODEX_HTTP_TESTS=1` |
| **Real windowed UI behaviour** | **nothing yet** — this runbook is that evidence |

A green CI run does not prove any row in the "Stages" tables below. Only your run does.

## Safety rules for this session

- Grant Accessibility (and Screen Recording only if you do stage 5) yourself in System Settings. Never
  let a script or this project change TCC, and never grant Terminal as a parent workaround.
- Use only the disposable fixture the self-check builds and launches. It contains synthetic text, a
  `DISPOSABLE-SYNTHETIC-SECRET` value and a 120-second self-termination timer.
- Do not run stage 7 while you have work in progress in a browser. It opens a **new window** in your
  existing browser at `https://example.com`. Existing tabs are not touched, but your browser will be
  activated.
- If a candidate build replaces the permission-approved preview, macOS may ask for permission again.
  Keep the current approved preview in place unless you deliberately choose to re-approve.

## Preconditions

1. macOS 14 or later, Xcode command line tools present (`xcode-select -p` succeeds).
2. The branch checked out: `git switch personal-codex/mac-automation` (tip at or after `7366121`).
3. Embedded frontend built once: `cd desktop && npm ci --ignore-scripts && npm run build`.

## Stage 0 — build and self-test (no permissions, ~2 min)

```sh
python3 scripts/build_mac_automation.py --self-test
```

Expect a JSON receipt: `application`, `binary`, `sha256`, `source_sha256`, `signature: "ad-hoc; not
notarized"`, `permissions_granted: false`, and one line of stdout from the helper stating
`self_tests_passed` (31) with `actual_ui_exercised: false`.

Evidence to keep: the printed `sha256` of the helper binary and the receipt.

**This does not build into the approved preview.** It writes to `desktop/automation/.build/`, a
separate path, and never overwrites the installed permission-approved app.

```sh
cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml -j 2
```

Expect 13 passing tests, one of them `#[ignore]` for the installed-model case.

```sh
cd desktop/automation && ./.build/Personal\ Codex\ Automation.app/Contents/MacOS/personal-codex-automation --status
```

Expect JSON with `accessibility`, `screen_capture`, `key_events` booleans. Record the starting values.

## Stage 1 — permissions and the panel

Open Personal Codex, open **Mac automation**. Confirm the three permission indicators. Use
"Request Accessibility permission" only if you intend to grant it; approve the macOS prompt yourself.
Re-check until Accessibility reads *available*.

## Stage 2 — synthetic self-check without capture (the core gate)

In the panel, open *Check automation with a disposable test app*, tick the consent box, leave capture
unticked, press **Run synthetic Mac check**. It launches its own fixture, drives it, then terminates
only that instance.

The panel prints a headline plus any failed check names. Required outcome: `All N checks passed.`
Each check below must appear as passed in the raw report shown under it:

| Check name | What it proves |
|---|---|
| `prepare_is_read_only` | Preparing a plan performs no action |
| `window_identity_refused` | A wrong title is refused, not obeyed |
| `window_number_identity_refused` | A wrong `AXWindowNumber` is refused (only present if the fixture exposes a number) |
| `native_text_and_press_result` | `set_text` + `press` reach the real AX tree and the postcondition matches |
| `approval_is_one_use` | The second use of the same approval is refused with `actionNotConfirmed` specifically |
| `native_checkbox_and_result` | Checkbox press plus result text |
| `native_scrollbar_result` | A real `AXScrollBar` value changed and matched |
| `stale_window_refused` | An external edit invalidates a prepared approval |
| `secure_control_omitted` | The secure field's value never appears in the serialized observation |
| `selected_window_isolation` | The protected window's content is absent from the primary snapshot |
| `cancelled_scope_refused` | A cancelled scope refuses further work |

If the run stops early, record `status`, `stage`, `error` and `completed_actions` from the summary.
`native_scrollbar_result` failing with `no editable scrollbar with a value was observed` means the
relationship walk found no usable bar — that is the known diagnostic path, not a pass.

## Stage 3 — capture, OCR and protected-window refusal (needs Screen Recording)

Grant Screen Recording to the helper app yourself, then repeat stage 2 with **Also check capture**
ticked. Two additional checks must pass:

| Check name | What it proves |
|---|---|
| `selected_window_capture_and_ocr` | Only the selected window is captured and OCR reads its synthetic heading |
| `secure_window_capture_refused` | Capturing the protected window is refused with `unsafeTarget` |

Confirm the panel preview image shows only the fixture window, never your desktop.

## Stage 4 — manual step path (no model)

With a scope on a running fixture window: choose control `Message`, action *Set text*, text `manual`,
verify control `Result` · value · `Preview: manual` **after** pressing Preview in a first step. Review
the shown plan, confirm the effect line says it focuses the selected window, approve once. Expect the
receipt "1 approved action(s) ran and the expected control matched." A second click must be refused.

## Stage 5 — cancellation and expiry

Start a plan, then press **Stop automation** before approving. Expect the scope to disappear and no
action to run. Start a new plan, wait more than two minutes, then approve: expect a refusal, not
execution. Record both messages verbatim.

## Stage 6 — local model against the synthetic window

With a fixture scope, tick the local-model consent, keep `qwen3.5:9b` selected (already installed; no
download occurs), and ask: `Enter hello in Message, press Preview, and verify Result is "Preview: hello".`
Review the returned plan's steps and expected value in the panel **before** approving. Then approve
once. Record: model name, proposal JSON, whether it validated, and the execution receipt.

A refusal here is a valid result to report verbatim — it is not a reason to weaken validation.

## Stage 7 — disposable browser window (last, and the largest untested area)

Prerequisites: Accessibility and keyboard-events permission. Finish or save browser work first.

1. Panel → *Start a fresh browser window* → choose Safari (or Chrome), address
   `https://example.com`, tick consent, press the button.
2. Expect `new_window_verified` and a scope whose origin is `https://example.com`.
3. Confirm in the browser that exactly one new window appeared and **every pre-existing tab is still
   open and unmodified**.
4. In the panel, prepare one safe step on the new window (for example a scroll or a key press) and
   approve it. Expect a verified result against that window only.
5. Negative check: start a second browser scope at `https://example.com`, then in the browser
   navigate that same window to `https://www.iana.org/` (any other origin) and refresh controls in the
   panel. Expect refusal with `targetChanged`, not silent control of the new origin.
6. Press **Stop automation** and confirm no further action is possible.

Do not type credentials anywhere in this stage. If the browser opens a tab instead of a window, record
that — it is a real finding about `⌘N` handling for that browser.

## Evidence to send back

For each stage: pass/fail, the exact check names from the panel, and any `stage`/`error` text. Paste
the JSON receipt from stage 0 (it contains hashes, no personal data). Nothing else is needed, and
nothing above requires sending window contents anywhere.

## Recording the result

After a stage passes, update `docs/RISK_REGISTER.md` (R-01, R-05, R-06, R-07, R-08, R-10) with the
date, macOS version, helper `sha256` and the observed check list. A stage only becomes
**Verified resolved** when its own run passed; a partial run leaves the rest untouched.
