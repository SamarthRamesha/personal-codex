# Personal Codex · owner acceptance handoff

Start from the published tip of `personal-codex/codex-integration` and its matching ARM64 GitHub artifact. Run the owner checklist with an isolated profile and disposable projects. Keep the current Automation Preview and permissions in place. [Owner testing guide](docs/FINAL_TESTING_GUIDE.md)

This release adds replacement proposals and fresh approvals after discard or cancellation, correction of saved project notes, and selection of declared npm checks into the existing approval flow. It retains launch-time installed-model selection, a selectable model for live calculator acceptance and archive checksum verification. [Product completeness and evidence](docs/PRODUCT_COMPLETION.md) Earlier verified browser demonstrations used scripted inference. Hosted CI also uses scripted inference.

## Remaining gates in order

1. On the M3, launch with a cached Ollama model. No paid AI service is required; the launcher seeds the local providers, and any other installed tag can be selected with `--model`. Run `scripts/offline_workstation.py --doctor` first. Verify streaming, stop, regeneration, model switching when two models are cached, and persisted chat and search.
2. Run the real calculator fixture and the reviewed coding and delivery checklist. Keep failure, repair, test and resume receipts with the candidate commit.
3. Run the Mac automation acceptance stages against synthetic fixtures. Record Accessibility, controls, scrolling, OCR, protected-window refusal, new-browser-window isolation and exact one-use approvals independently.
4. Review the JARVIS deployment requirements with the owner. The host is reported online. This workspace had no authorized connection available. Deployment, private HTTPS routing and the persistent worker require separate approval and target verification. [Deployment plan](DEPLOYMENT.md)

Commit and push explicitly only to `personal-codex/codex-integration`. Preserve the unresolved `main` incident, model caches, application profiles, private checkpoints and the approved preview. Never read, edit, stage, delete or upload `personal-codex-diagnostic.txt`. Preserve `web/style.css`, `web/chat.js`, `.recovery-backup/`, `.safety/`, `diagnostics/` and `SESSION_HANDOFF.md`. The owner grants Mac permissions. Preserve TCC and all JARVIS family services.
