# Handoff

The repository is recoverable without chat history. Start with `PROJECT_STATUS.md`, then verify with `git status`, `README.md`, and the unit-test command. The approval-gated worktree command runner, recovery-branch lifecycle, provider metadata validation, approval-gated invocation lifecycle, and real Ollama/OpenAI-compatible HTTP transports are implemented. No live model or external provider has been exercised — adapter tests use a loopback stub — and there is still no agent engine, so do not claim autonomous code modification.

Current highest-priority task: implement the first bounded developer-agent cycle — a strict allowlisted tool-call schema produced from an approved provider response, an approval-gated file-edit tool confined to the task worktree, and test-result recording. Never send a prompt to a cloud endpoint without the recorded `network` approval, and never let model output execute outside the allowlist.

Never add server access or cloud credentials to the repository. Update all checkpoint documents after every meaningful milestone.

Cross-account continuation is a permanent project requirement. After each meaningful verified milestone, regenerate `NEXT_SESSION_PROMPT.md` from actual Git/repository state; immediately do the same and display it when the user requests a handoff; and do so before usage exhaustion. Every generated prompt must contain the dedicated `PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL` section and require the next account to repeat this process.

Treat every completed user request or development phase as a handoff-refresh checkpoint: update `NEXT_SESSION_PROMPT.md` from actual state before reporting completion, then commit/push it with meaningful verified work when available.

GitHub continuity is permanent. The official remote is `origin` at `https://github.com/SamarthRamesha/personal-codex.git`; commit meaningful verified milestones and push to `main` when available. Verify remote state first, never force-push or overwrite unexpected history, and record unpushed commits if publication is unavailable.
