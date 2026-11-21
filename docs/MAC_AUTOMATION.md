# Mac automation preview

This branch adds reviewed text reading, control presses, text entry, keyboard navigation, scrolling and optional selected-window capture/OCR. It is a preview, not an accepted general-purpose Mac operator. The stable opening actions remain available separately.

## What is implemented

| Capability | Behavior | Acceptance status |
| --- | --- | --- |
| App and window selection | Choose a running application and a specific window; consent lasts up to ten minutes or 32 actions | Implemented; actual target UI unverified |
| Accessibility reading | Bounded control tree, labels and supported values; secure and recognized credential controls omitted | Native helper builds; real secure-field check pending permission |
| Review and execution | One to eight explicit actions, one-use approval, two-minute expiry, fresh observation digest | Policy and transport tests pass |
| Text, presses, keys, scrolling | Public Accessibility APIs and targeted Enter/Tab/Escape; checks focus and window identity | Production driver implemented; real UI checks pending |
| Local natural-language plan | Existing local Ollama 9B or 14B proposes actions from selected text, after separate consent | Installed local 9B synthetic trial passed; no real-window or general reliability claim |
| Browser workflows | New window is observed before its address is entered; scope binds the page origin | Implemented; actual browser acceptance pending |
| Screenshot and OCR | Separate permission and consent; captures a unique selected window, refuses incomplete/protected safety context | Implemented; actual capture acceptance pending |
| Stop | Out-of-band stop invalidates scope and pending proposals, kills only this app's helper | Bounded transport/cancellation tests pass; in-flight edits may remain |
| Synthetic self-check | Bundled disposable test app checks native text/press, checkbox, scrollbar, stale observation, protected-field omission and cancellation | Refuses to act while Accessibility is unavailable |

No backend route exposes these capabilities. A JARVIS backend cannot select Mac windows or execute these native commands.

## Try the preview

The preview is built separately from the stable application. On the prepared Mac, use the local preview location listed in the private checkpoint. For a source build:

```sh
python3 scripts/build_mac_automation.py --self-test
cd desktop
npm ci --ignore-scripts
npm run tauri -- build --bundles app --config '{"productName":"Personal Codex Automation Preview","identifier":"local.personalcodex.desktop.automationpreview"}'
codesign --force --sign - "src-tauri/target/release/bundle/macos/Personal Codex Automation Preview.app"
codesign --verify --deep --strict "src-tauri/target/release/bundle/macos/Personal Codex Automation Preview.app"
```

The helper requires macOS 14 or later and Apple's installed Swift compiler. The build does not grant permissions or download models. The app is signed ad hoc, not notarized.

1. Open the preview and choose **Mac automation** in its sidebar. A backend connection is unnecessary.
2. Choose **Request Accessibility permission**, then manually approve only the named Personal Codex application in macOS Privacy & Security. Check permissions again; a restart may be required.
3. Use **Check automation with a disposable test app**. Review its description, confirm, and run the check. It uses synthetic windows and terminates only the exact test app it launches. It does not inspect personal apps. The fixture also expires after two minutes if a cancelled helper cannot clean it up.
4. For optional screen reading, separately request Screen & System Audio Recording permission for the named app. Do not grant Terminal or another parent app as a workaround. Run the capture check only after granting and checking that permission.
5. For ordinary use, select the app and window, inspect its controls, describe the goal, consent to local inference, and review the exact actions and changed result to verify. A plan proposal alone never means the task ran.
6. Use **Stop automation** or close the panel to discard scope. Inspect the target before retrying an interrupted action.

macOS permissions are broader than this application's window scope. They let the approved process access other applications; this implementation adds its own narrower scope. Never grant an unexpected executable or bypass the operating system's permission controls.

## Limits that affect safe use

- Public Accessibility support varies by app. Custom canvas controls, games, unlabeled controls and unsupported widgets are refused or unavailable. Arbitrary coordinate clicking, drag/drop, arbitrary shortcuts and unrestricted shell control are not implemented.
- Known security, password-manager, terminal and development applications are blocked. Recognized consequential labels are refused. These are heuristic checks, not a complete classifier for every language or business consequence. Read each plan and use trusted apps/sites.
- Secure fields and recognizable credential patterns are omitted. Ordinary documents can still contain sensitive information that these checks cannot recognize. Local model consent is required; screenshots are not automatically sent to a model or saved.
- Browser scope checks origin and omits foreign-origin web areas. This is not a browser sandbox, a guarantee that a website is benign, or a promise that every supported browser version works. Existing browser tabs are not navigated by the new-window adapter; it may briefly focus the browser.
- A changed UI, ambiguous response, timeout, revoked permission or stopped scope invalidates approval. There is no automatic action retry or rollback; completed edits remain.
- Verification means only the exact displayed control matched the approved expected text. It does not establish arbitrary task correctness or production readiness.
- Real native app, browser, screenshot/OCR and local-model-to-real-UI checks are required before priority 1 is complete. Tests that use an in-memory driver do not satisfy them.

## Checks and evidence

The source contains 31 helper policy checks, 13 passing Rust checks (plus one explicit installed-model test ignored by normal CI), and 17 frontend checks. These test invariants and contracts, not universal app compatibility. The optimized preview build passes. The owner granted all three product permissions. The first actual native self-check stopped with `targetChanged`; it did not pass. The focus-handling revision requests the exact bound window as main/focused and waits for both app and window focus without weakening the pre-action checks. It also returns the failed stage and bounded synthetic target metadata before cleanup. A real UI rerun is required; no personal app was used.

Private logs retain failed model trials and the corrected local 9B pass (two synthetic actions, exact result matched). Do not treat a later pass as proof that every natural-language request works. Hosted CI runs policy/build checks without UI grants, personal files, local models or JARVIS credentials.

## Resume order

1. Finish actual Mac automation acceptance, including a disposable browser workflow and capture/OCR if approved. Fix observed issues without weakening approval or permission checks.
2. Visually accept the older opening panel.
3. Reassess JARVIS read-only, preserve family access and obtain exact deployment approvals.
4. Broaden development workflows.
5. Complete production operations, isolation, recovery and distribution.

Do not advance to a later priority while the first remains unaccepted.
