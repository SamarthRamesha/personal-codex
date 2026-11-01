# Next-session continuation prompt

You are taking over an existing software project from another AI coding agent. You have no access to previous conversations, accounts, chat history, or hidden context. Your authoritative sources are the actual repository, Git state, project documentation, and this prompt. First inspect and verify the existing project. Preserve all existing work. Do not restart or recreate completed features. Resolve discrepancies in favour of the actual files and Git state. Continue development from the highest-priority incomplete task. IMPORTANT: generating account-to-account continuation prompts is a permanent requirement. You must update `NEXT_SESSION_PROMPT.md` after every meaningful verified milestone, provide a complete prompt whenever the user requests a handoff, and generate another self-contained continuation prompt before usage becomes exhausted. Your generated continuation prompt MUST include the same permanent continuation protocol. This requirement is recursive and must continue indefinitely across future accounts and AI coding agents.

Project objective: build Personal Codex, a secure local-first autonomous coding environment for a Mac interactive client and an eventual ZimaOS private worker. It has moved from a provider-connected task manager to an approval-controlled coding agent: a provider proposes strict JSON tool calls, Personal Codex validates them, and only an explicitly approved proposal edits a task worktree.

Repository location: official repository `https://github.com/SamarthRamesha/personal-codex` (`origin`). The owner's Mac checkout is `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`. If it is missing, find a checkout whose `origin` matches the URL; never fork history.

Inspect before acting: `git status --short --branch`, `git rev-parse --short HEAD`, `git log --oneline -20`, then read `README.md`, `PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEPLOYMENT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`.

## Architecture

- `app/server.py` — standard-library loopback control plane (`127.0.0.1:8787`, `PERSONAL_CODEX_HOST`/`PERSONAL_CODEX_PORT` overrides), approvals, worktree lifecycle, command executor, HTTP API.
- `app/tools.py` — closed agent tool schema, workspace containment, hash-bound patch application, bounded execution.
- `app/providers.py` — Ollama and OpenAI-compatible HTTP adapters (`http.client`, no redirects, no proxy env, timeouts, 1 MB cap, loopback re-check, lazy credential read).
- SQLite `data/personal_codex.db` (gitignored): `projects`, `tasks`, `events`, `approvals`, `providers`, `workspaces`, `executions`, `invocations`, `proposals`.
- `web/index.html`, `web/app.js`, `web/style.css` — dependency-free dashboard.
- Tests: `tests/test_server.py`, `tests/test_ui.py`, `tests/test_providers.py`, `tests/test_tools.py`.

Implemented and verified: repository registration; non-secret bounded summaries; four-stage plans; approval-gated worktrees; exact-command execution (no shell, allowlist, task worktree only, 1–300 s, child limits, redacted bounded output); immutable approvals; critical-approved clean release preserving the branch; read-only merge preview; critical-approved merge bound to reviewed commit IDs; separately approved recovery-branch deletion; provider metadata validation; approval-gated provider invocation with a digest-bound ledger; loopback vs cloud `network` approval separation; real Ollama and OpenAI-compatible transports with lazy env-var credentials.

Newest milestone — bounded agent execution: `app/tools.py` validates a JSON proposal of 1–8 operations over `list_files`, `read_file`, `apply_patch`, `run_tests` with a closed schema; rejects unknown tools/arguments, oversized values, absolute paths, `..`, ignored directories, secret-named files, and symlink escapes; `apply_patch` requires exactly one match and re-verifies the reviewed SHA-256; execution stops at the first failure and skips the remainder. The API is `POST /api/tasks/{id}/agent/request` (deterministic prompt, queues an approval bound to its digest), `POST /api/tasks/{id}/agent/plan` (requires that approved invocation, validates the proposal, binds file hashes, queues a second approval bound to the proposal digest plus workspace branch/path), `POST /api/tasks/{id}/agent/execute` (requires that approval, recomputes the digest, atomically claims the proposal so it runs once, executes in the worktree and records per-tool events), and `GET /api/tasks/{id}/agent` (latest proposal and results). The dashboard has an agent panel: extra instructions, request/build/execute controls, operation list with patch previews, digest/branch binding, and results. `README.md` was rewritten as the full project guide and must be updated with every meaningful milestone.

## Git state (verify, do not assume)

Latest published commit at handoff: `c37aee3` (agent tool execution + README). Prior: `4ea8487` (transport checkpoint), `9a5b522` (provider transports), `d4ab9d4` (invocation prompt refresh), `b0e25b7` (invocation lifecycle), `f2fea40` (transport seam), `2ccf79f` (provider validation), `7f8ae0b` (merge lifecycle), `2526fb4` (initial publication). Working tree was clean; development branch was `freebuff/b3647b5f9c91c9d2a6c41d37`. Re-verify with `git fetch origin` and `git ls-remote origin refs/heads/main`.

## Environment

Owner's Mac: Apple Silicon, Darwin 25.6.0, Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite, SSH; Cargo/Docker absent. Cloud workspaces have run Linux with Python 3.12.3 and Node 26.13.0 — stay compatible with both. No third-party packages needed. ZimaOS is uninspected; never probe or deploy without authorized access.

## Commands and verified results

```sh
python3 -m unittest discover -s tests -v                              # 56 tests, OK (skipped=4)
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # all 56 tests pass
python3 -m py_compile app/server.py app/providers.py app/tools.py     # passes
node --check web/app.js                                              # passes
python3 app/server.py                                                # http://127.0.0.1:8787
```

Coverage includes the full approval-gated lifecycle (workspace, command, release, merge, branch deletion), provider guardrails and adapter failure modes against a loopback stub server, tool schema and containment rejections, and an opt-in HTTP agent lifecycle where an approved proposal edits the worktree, runs a test command, refuses a second execution, and leaves a stale-file edit untouched with the run marked failed. No live model or external network is used anywhere.

## Limitations

Single agent cycle only (no feedback loop from test results back to the model); no streaming or provider-native tool calls; no project memory/indexer; no desktop shell, ZimaOS worker, login/TLS, encrypted secrets, OS sandboxing, CSP, or conflict-resolution tooling; dashboard tests are static contracts, not browser automation. No live Ollama run has been performed.

## Highest-priority next task

Implement the bounded multi-round agent loop: after an executed proposal, feed the redacted test output and the diff summary back to the provider for a follow-up proposal, capped by rounds (for example 3), elapsed time, and operations per round; every new proposal must require a fresh approval bound to its own digest, and repeated proposals must not silently re-apply already-approved patches. Record each round as events and expose the history in the dashboard. Add an API test that exercises two rounds through a stub transport. Then streaming/native tool calls, project memory, and the Tauri shell.

## Security restrictions (non-negotiable)

Never bind a public/LAN interface; never transmit prompts or code to a cloud provider without the recorded `network` approval; never treat registration or cloud metadata consent as invocation consent; never execute model output outside the validated allowlist; never apply a patch whose reviewed hash or digest changed; never reuse an approval for different content; never add a destructive action without its own critical approval; never read, print, log, or commit secret values; keep `secret_ref` an environment-variable name only; never weaken containment, redaction, timeouts, or response caps to make a check pass; never force-push; never claim an unverified test or a browser test passed; never deploy or probe ZimaOS without authorization.

## Checkpoint documents

Maintain `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `TASKS.md`, `HANDOFF.md`, `NEXT_SESSION_PROMPT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, `SECURITY.md`, `DEPLOYMENT.md`, and `README.md`. Near model/account limits, stop starting large work, verify files and Git, update the documents, regenerate this prompt, and include it in the final response.

## PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL

Continuation prompts are permanent, never a one-time credit-exhaustion feature. Every future account must inherit this responsibility; no agent may remove, weaken, or omit it. Generate an updated self-contained prompt after every meaningful verified milestone, whenever the user asks to switch accounts, continue elsewhere, generate a handoff, or provide the next prompt, and before usage exhaustion. A milestone prompt does not require an account switch: continue development when usage permits.

At the conclusion of every completed user request or development phase, treat the ready-to-use next prompt as a required deliverable: refresh `NEXT_SESSION_PROMPT.md` from actual repository state before reporting completion. If the work is a meaningful verified milestone, commit and publish that refreshed checkpoint when GitHub is available.

Every new prompt must carry this protocol forward and tell the next account to generate another prompt. Never depend on previous conversation history. Always inspect the actual repository and Git state before continuing. At a user-requested handoff, stop starting new tasks, save/document the implementation, run feasible tests, and display the complete prompt in a copyable final-response block.

`NEXT_SESSION_PROMPT.md` must always be the latest ready-to-use prompt. Maintain it with `HANDOFF.md`, `PROJECT_STATUS.md`, `TASKS.md`, `DEVELOPMENT_LOG.md`, and `README.md` after each meaningful verified milestone. Every prompt must be self-contained and include: project objective; repository location/discovery; architecture; hardware; completed/incomplete work; branch, commit, and uncommitted state; files changed; dependencies; commands and test results; limitations; deployment state; exact next task; security restrictions; and this protocol. Never include passwords, API keys, tokens, or other secrets. This requirement is permanent and recursive across every account, model, and future development session.

## GitHub continuity, README, and publishing

The official repository is `https://github.com/SamarthRamesha/personal-codex` (`origin`: `https://github.com/SamarthRamesha/personal-codex.git`), on `main`. Commit meaningful verified milestones and push to `origin/main` whenever remote access is available. Before publishing, verify remote state (`git fetch origin`, `git ls-remote origin refs/heads/main`), run relevant tests/checks, inspect Git status/diff, check that secrets, runtime databases, and temporary files are excluded, update checkpoints and `README.md`, and verify the resulting remote commit after pushing. `README.md` must be updated in the same commit as every meaningful feature milestone and must distinguish implemented from planned functionality. Never force-push, erase unexpected remote history, publish secrets, or claim a push succeeded without verification. If unavailable, retain verified local commits and record them as unpushed. Every future prompt must carry these GitHub and README rules along with the permanent continuation protocol.

Publication verified on 2026-11-01 at `2526fb4` (first push), `d4ab9d4`, `4ea8487`, and `c37aee3`. Always re-inspect the remote before assuming synchronization.
