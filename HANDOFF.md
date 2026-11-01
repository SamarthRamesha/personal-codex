# Handoff

The repository is recoverable without chat history. Start with `PROJECT_STATUS.md`, then verify with `git status`, `README.md`, and the unit-test command. The approval-gated worktree command runner, recovery-branch lifecycle, provider metadata validation, approval-gated invocation lifecycle, real Ollama/OpenAI-compatible transports, the single-cycle agent tool dispatcher, and the persistent multi-round loop are implemented. No live model or external provider has been exercised — adapter and round tests use an injected loopback transport — so do not claim verified autonomous coding by a real model.

Current highest-priority task: the first real Ollama round on the owner's Mac (Python 3.13.9, Apple Silicon), because every round so far was driven by a deterministic injected transport. Execution reliability is now in place: per-operation cancellation, an operation ledger with interrupted-operation recovery, cumulative budgets with explicit reset, a bounded repository context engine, and a project-memory foundation. Next after the live run: streaming/native tool calls and automatic memory promotion from verified rounds.

The multi-round loop is `round/request` → approval → `round/plan` → proposal approval → `round/execute`, capped at 3 rounds (`PERSONAL_CODEX_MAX_ROUNDS`), 1 800 seconds per task, and 8 operations per round. Every round gets a fresh approval bound to its round number, prompt digest, workspace branch/path, and proposal digest; file hashes are re-verified at execution, duplicate provider responses are refused, and completion is only accepted with a passing test run plus an approved file change.

Never add server access or cloud credentials to the repository. Update all checkpoint documents after every meaningful milestone.

Cross-account continuation is a permanent project requirement. After each meaningful verified milestone, regenerate `NEXT_SESSION_PROMPT.md` from actual Git/repository state; immediately do the same and display it when the user requests a handoff; and do so before usage exhaustion. Every generated prompt must contain the dedicated `PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL` section and require the next account to repeat this process.

Treat every completed user request or development phase as a handoff-refresh checkpoint: update `NEXT_SESSION_PROMPT.md` from actual state before reporting completion, then commit/push it with meaningful verified work when available.

GitHub continuity is permanent. The official remote is `origin` at `https://github.com/SamarthRamesha/personal-codex.git`; commit meaningful verified milestones and push to `main` when available. Verify remote state first, never force-push or overwrite unexpected history, and record unpushed commits if publication is unavailable.
