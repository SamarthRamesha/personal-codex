# Project status

Updated 22 November 2026. **Partially complete. Mac automation is a preview; JARVIS is not deployed.**

The active branch is `personal-codex/mac-automation`, based on the preserved stable source `64189ef30177922481d17da242d11a90baf3c599`. The stable launcher/profile has not been replaced by this preview.

## Current priority: general Mac automation

Implemented selected-window Accessibility reading, reviewed text/press/key/scroll actions, optional window capture/OCR, local Ollama proposals, browser new-window scoping and bounded cancellation. A disposable synthetic app and native self-check are bundled. The owner granted product permissions; the first actual native self-check stopped with targetChanged. A focus-handling revision and stage diagnostics are prepared for rerun.

31 helper checks, 13 Rust checks and 41 frontend checks pass; the backend suite is 415 tests with `PERSONAL_CODEX_HTTP_TESTS=1` (one skip needs the optional `cryptography` wheel). The optimized preview builds and the hosted `native` job compiles and self-tests the helper. One installed local 9B trial passed the actual policy with an in-memory driver after an earlier fixture mismatch was corrected; it did not act on a real window. Actual native, browser, capture/OCR and natural-language-to-real-UI acceptance remain pending. [Behavior and limits](docs/MAC_AUTOMATION.md).

The last two sessions closed seventeen provable defects, each with a check that fails on the old code: approval replay and approval lifetime (a stale approval authorized commands, cloud invocations and setup routes), the acceptance summariser's exit codes and `NOT EXERCISED` lines, unscreened OCR text on capture, restore-tree permissions, output redaction that corrupted proposals, a leaked chat generation slot, false completion evidence, a leaked coding-run slot, an unlisted self-check status shown as a pass, secret-shaped files selected into prompts, chat regeneration that asked the model to continue its own answer, and connection resets on unexpected handler errors. [Risk register](docs/RISK_REGISTER.md) has 29 rows with evidence and limits.

## Preserved local functionality

Native chat/history/streaming, existing local models, reviewed coding tasks, worktrees, repair/checks/delivery, explicit resume, memory integrity, attributed document search, bounded exact proposal-cycle detection and the previous reviewed opening actions remain in source. Backend and frontend source both changed in this preview and are covered by its own suite and hosted checks; nothing here is certified as a JARVIS deployment.

## Remaining order

1. Actual general Mac automation acceptance and fixes.
2. Visual acceptance of the earlier opening panel.
3. JARVIS HTTPS/backend deployment, image/import/ownership and family-access review with exact approvals.
4. Broader development workflows.
5. Production isolation, encrypted recovery at larger scale, hard quotas and notarized distribution.

Do not advance past priority 1 while it is incomplete. No server, Docker, networking, Tailscale policy or family-data changes were made in this phase. Local OS permissions require the owner; no authentication bypass is permitted.

This preview branch has its own hosted checks. Historical green stable runs do not certify its new UI. See [continuation](NEXT_SESSION_PROMPT.md) and the private checkpoint for current commit/build/check receipts.
