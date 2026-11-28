# Product completion inventory

Baseline `c588e90e5de8f07bf063e68f55748f7d83358867`, verified on 28 November 2026. The hosted run passed backend, desktop and macOS jobs and published the ARM64 artifact. This workspace is Linux with no reachable Ollama and no authorized Mac or JARVIS connection. [Baseline run #121](https://github.com/SamarthRamesha/personal-codex/actions/runs/46041472113)

| Capability | Classification | Evidence and next gate |
|---|---|---|
| Offline launcher and release packaging | Implemented and integration-tested | macOS CI starts the authenticated backend with a scripted inventory, checks cleanup, signs and archives the ARM64 app. First launch and permissions on the M3 remain open. |
| AI providers and chat | Implemented and integration-tested | Local-only inventory, explicit provider choice, conversation streaming, cancellation, regeneration and persisted messages have scripted and HTTP coverage. Current installed-model acceptance is blocked here. Optional external inference is explicit and scoped to approved task flows. |
| History, memory and documents | Partially implemented | Desktop history, search, attribution, project notes and document indexing are wired and covered. The desktop can correct saved memory through the project-scoped server route. Edits become owner notes. |
| Supervised coding and orchestration | Partially implemented | Scripted repair, reviewed execution, delivery and persistence have end-to-end evidence. HTTP tests cover discarding a reviewed proposal, revoking its approval, binding execution to the displayed proposal, and obtaining a fresh planning approval after cancellation. Broader full-stack workflows and live-model repair remain open. |
| Dependencies and dev servers | Partially implemented | Worktree readiness shows declared commands and markers, and supported npm checks can be placed directly in the existing approval flow. Owners manage installs and development servers in a terminal. Network-enabled app-managed install and server lifecycle are missing. |
| Native Mac controls, capture and OCR | Implemented but not accepted on target hardware | Swift/Rust policy tests and synthetic helper compile in CI. Current selected-window, focus, scroll, protected capture and OCR checks need the owner’s M3. |
| Browser automation | Implemented but not accepted on target hardware | Reviewed new-window and origin-scoped actions exist. Real-browser isolation, form interaction and stale-window refusal need synthetic target acceptance. Broader multi-page workflows remain limited. |
| Interruption and recovery | Implemented and integration-tested | SQLite restart drills, scripted full-task resume, bounded recovery and delivery preservation are covered. Large-scale encrypted restore and cross-device sync are missing. |
| JARVIS | Blocked by unavailable authorization and environment | Private HTTPS profile, outbound model worker, separate credentials, local deployment checks and rollback design exist. Current target connectivity, storage, service isolation and family-access preservation require authorized verification. |
| Production distribution | Partially implemented | Reproducible ad-hoc ARM64 artifacts and checksums exist. Developer ID notarization and managed updates are missing. |

The owner can exercise the local application using the isolated candidate profile. Current real-model and native GUI acceptance remain separate gates. [Owner guide](FINAL_TESTING_GUIDE.md)

## Optional server data

Keep each backend profile as the authority for its own data. The offline profile stays on the Mac, and a future JARVIS profile stores sessions created while connected to that backend. A reconnect returns to the chosen profile. There is no automatic cross-profile synchronization. For an authorized migration, take a verified backup, restore into an isolated destination and review any conflicting project revisions through Git before moving work. Keep the old profile available for rollback. [Deployment gates](../DEPLOYMENT.md)
