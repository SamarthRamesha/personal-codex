# Handoff

The repository is recoverable without chat history. Start with `PROJECT_STATUS.md`, then verify with `git status`, `README.md`, and the unit-test command. The approval-gated worktree command runner and recovery-branch lifecycle are implemented. Provider metadata validation and the approval-gated invocation lifecycle are implemented, but the shipped transport fails closed: no real Ollama or OpenAI-compatible network client exists yet, so do not claim autonomous code modification or live model execution before an agent engine and a real transport exist.

Current highest-priority task: implement a real Ollama transport behind the existing injected seam (still approval-gated, still loopback-only without `network` consent), verified first against a local stub server. Never send a prompt to a cloud endpoint without the recorded `network` approval.

Never add server access or cloud credentials to the repository. Update all checkpoint documents after every meaningful milestone.

Cross-account continuation is a permanent project requirement. After each meaningful verified milestone, regenerate `NEXT_SESSION_PROMPT.md` from actual Git/repository state; immediately do the same and display it when the user requests a handoff; and do so before usage exhaustion. Every generated prompt must contain the dedicated `PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL` section and require the next account to repeat this process.

Treat every completed user request or development phase as a handoff-refresh checkpoint: update `NEXT_SESSION_PROMPT.md` from actual state before reporting completion, then commit/push it with meaningful verified work when available.

GitHub continuity is permanent. The official remote is `origin` at `https://github.com/SamarthRamesha/personal-codex.git`; commit meaningful verified milestones and push to `main` when available. Verify remote state first, never force-push or overwrite unexpected history, and record unpushed commits if publication is unavailable.
