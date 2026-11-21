# Project status

Updated 21 November 2026. **Partially complete. Mac automation is a preview; JARVIS is not deployed.**

The active branch is `personal-codex/mac-automation`, based on the preserved stable source `64189ef30177922481d17da242d11a90baf3c599`. The stable launcher/profile has not been replaced by this preview.

## Current priority: general Mac automation

Implemented selected-window Accessibility reading, reviewed text/press/key/scroll actions, optional window capture/OCR, local Ollama proposals, browser new-window scoping and bounded cancellation. A disposable synthetic app and native self-check are bundled. The self-check correctly reports permission required before touching any UI.

31 helper checks, 13 Rust checks and 17 frontend checks pass. The optimized preview builds. One installed local 9B trial passed the actual policy with an in-memory driver after an earlier fixture mismatch was corrected; it did not act on a real window. Actual native, browser, capture/OCR and natural-language-to-real-UI acceptance remain pending. [Behavior and limits](docs/MAC_AUTOMATION.md).

## Preserved local functionality

Native chat/history/streaming, existing local models, reviewed coding tasks, worktrees, repair/checks/delivery, explicit resume, memory integrity, attributed document search, bounded exact proposal-cycle detection and the previous reviewed opening actions remain in source. The previous backend result was 372 passed / 5 skipped / 377 discovered. Backend source is unchanged by this preview and was not re-certified as a JARVIS deployment.

## Remaining order

1. Actual general Mac automation acceptance and fixes.
2. Visual acceptance of the earlier opening panel.
3. JARVIS HTTPS/backend deployment, image/import/ownership and family-access review with exact approvals.
4. Broader development workflows.
5. Production isolation, encrypted recovery at larger scale, hard quotas and notarized distribution.

Do not advance past priority 1 while it is incomplete. No server, Docker, networking, Tailscale policy or family-data changes were made in this phase. Local OS permissions require the owner; no authentication bypass is permitted.

This preview branch has its own hosted checks. Historical green stable runs do not certify its new UI. See [continuation](NEXT_SESSION_PROMPT.md) and the private checkpoint for current commit/build/check receipts.
