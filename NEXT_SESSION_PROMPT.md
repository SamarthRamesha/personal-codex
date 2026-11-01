# Next-session continuation prompt

You are taking over an existing software project from another AI coding agent. You have no access to previous conversations, accounts, chat history, or hidden context. Your authoritative sources are the actual repository, Git state, project documentation, and this prompt. First inspect and verify the existing project. Preserve all existing work. Do not restart or recreate completed features. Resolve discrepancies in favour of the actual files and Git state. Continue development from the highest-priority incomplete task. IMPORTANT: generating account-to-account continuation prompts is a permanent requirement. You must update `NEXT_SESSION_PROMPT.md` after every meaningful verified milestone, provide a complete prompt whenever the user requests a handoff, and generate another self-contained continuation prompt before usage becomes exhausted. Your generated continuation prompt MUST include the same permanent continuation protocol. This requirement is recursive and must continue indefinitely across future accounts and AI coding agents.

Project objective: build Personal Codex, a secure local-first autonomous coding environment for a Mac interactive client and an eventual ZimaOS private worker.

Repository location: official repository `https://github.com/SamarthRamesha/personal-codex` (`origin`). The owner's Mac checkout is `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`. If that path is missing, find a checkout whose `origin` matches the URL above; do not fork history.

Inspect before acting: `git status --short --branch`, `git rev-parse --short HEAD`, `git log --oneline -20`, then read `README.md`, `PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEVELOPMENT_LOG.md`, `CHANGELOG.md`, `DEPLOYMENT.md`.

## Architecture

- `app/server.py` — standard-library loopback control plane (`127.0.0.1:8787`, overridable via `PERSONAL_CODEX_HOST`/`PERSONAL_CODEX_PORT`), `ThreadingHTTPServer`.
- `app/providers.py` — standard-library provider HTTP adapters (Ollama, OpenAI-compatible).
- SQLite at `data/personal_codex.db` (gitignored): `projects`, `tasks`, `events`, `approvals`, `providers`, `workspaces`, `executions`, `invocations`.
- `web/index.html`, `web/app.js`, `web/style.css` — dependency-free dashboard.
- `tests/test_server.py`, `tests/test_ui.py`, `tests/test_providers.py` — stdlib `unittest`; no installed packages.

Implemented and verified: project registration; bounded non-secret repository summaries; four-stage planner/developer/testing/reviewer plans; approval-gated worktree creation; exact-command execution (no shell, allowlist, task workspace only, 1–300 s timeout, child CPU/file/descriptor/address-space limits, 200 kB redacted output); immutable one-way approvals; critical-approved clean release retaining a recovery branch; read-only merge preview + conflict reporting; critical-approved merge bound to reviewed source/target commits (stale state rejected); separately approved recovery-branch deletion (ancestry-checked, commit-bound); provider metadata validation (absolute HTTP(S), no embedded credentials, loopback unless `cloud_allowed: true`, `secret_ref` = environment-variable name only, no secret read or provider contact at registration).

Newest milestone: real approved provider invocation. `POST /api/tasks/{id}/provider-request` records a pending approval bound to task, provider ID, endpoint, model, prompt SHA-256, and cloud flag; `POST /api/tasks/{id}/invoke` requires that exact approved record. Loopback providers need kind `provider-invoke`; cloud-consented providers need a separate `network` approval. `app/providers.py` implements Ollama `/api/chat` (and `/api/generate`) and OpenAI-compatible `/chat/completions` using `http.client` (proxy env vars ignored, redirects refused, 60 s timeout, 1 MB response cap, sanitised errors, loopback re-check inside the adapter). OpenAI credentials are read from the named environment variable inside the transport at call time, used only in the `Authorization` header, never stored or logged; cloud providers require a secret reference and missing credentials fail before sending. `server.PROVIDER_TRANSPORT` defaults to `None` (built-in adapters); setting it to a callable injects a deterministic transport, and `unavailable_provider_transport` restores hard fail-closed behaviour. Responses are bounded, redacted, stored in `invocations` with the prompt digest (never the prompt), listed at `GET /api/tasks/{id}/invocations`, and audited. Dashboard has provider select with transport-policy hint, approval request, duplicate-guarded invoke, and a response ledger.

## Git state (verify, do not assume)

Published through the milestone before the transport work at `d4ab9d4`; the transport milestone was committed locally as `9a5b522` and published immediately after. Always run `git status --short --branch`, `git rev-parse --short HEAD`, and `git ls-remote origin refs/heads/main`. Recent commits: `9a5b522` (transports), `d4ab9d4` (prompt refresh), `b0e25b7` (invocation lifecycle), `f2fea40` (transport seam), `2ccf79f` (provider validation), `7f8ae0b` (merge lifecycle), `2526fb4` (initial publication).

## Environment

Owner's Mac: Apple Silicon, Darwin 25.6.0, Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite, SSH; Cargo/Docker absent. Cloud workspaces have run Linux with Python 3.12.3 and Node 26.13.0 — stay compatible with both. No third-party packages installed or needed. ZimaOS is uninspected; never probe or deploy without authorized access.

## Commands and verified results

```sh
python3 -m unittest discover -s tests -v                              # 40 tests, OK (skipped=2)
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # all 40 tests pass
python3 -m py_compile app/server.py app/providers.py                  # passes
node --check web/app.js                                              # passes
python3 app/server.py                                                # http://127.0.0.1:8787
```

The opt-in suite covers registration → task → provider guardrails → denied/approved workspace → denied/approved command → provider invocation denied/approved/invoked → changed-prompt rejection → ledger → cloud `network` approval separation → clean release → merge preview → stale-approval rejection → merge → branch deletion, plus a no-override test hitting the built-in Ollama adapter through a stub loopback model server. `tests/test_providers.py` covers request path/shape, response extraction, malformed JSON, HTTP 500, redirect refusal, connection refusal, timeout, oversize, unexpected structure, invalid endpoints, non-loopback refusal, credential handling, and transport selection.

## Limitations

No provider streaming, no tool-call execution, no agent engine that edits code, no native desktop shell, no server connector, no indexer/LSP, no encrypted secret store, no login/auth, no TLS/remote protocol, no CSP, no OS sandboxing, no conflict-resolution tooling, no browser-automation UI tests. No live Ollama or cloud call has been made — all adapter tests use a local stub. Nothing is deployed; ZimaOS work is deferred.

## Highest-priority next task

Implement the first bounded developer-agent cycle on top of the approved provider invocation: define a strict tool-call schema (`apply_patch`/`write_file`, `read_file`, `run_tests`) returned as validated JSON; execute only allowlisted tools, only inside the task worktree, only after the approvals that already gate workspace creation and command execution; record tool calls and test results as immutable events. Extend provider adapters with streaming and tool-call parsing only after the allowlisted dispatcher exists. Add UI coverage for the new controls. Then project-memory rebuild and the Tauri shell.

## Security restrictions (non-negotiable)

Never bind a public/LAN interface; never transmit prompts or code to a cloud provider without the recorded `network` approval; never treat registration or cloud metadata consent as invocation consent; never execute model output outside the tool allowlist; never add a destructive action without its own critical approval; never read, print, log, or commit secret values; keep `secret_ref` an environment-variable name only; never weaken approval binding, redaction, workspace containment, timeouts, or response caps to make a check pass; never force-push; never claim an unverified test passed; never deploy or probe ZimaOS without authorization.

## Checkpoint documents

Maintain `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `TASKS.md`, `HANDOFF.md`, `NEXT_SESSION_PROMPT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, `SECURITY.md`, `DEPLOYMENT.md`. Near model/account limits, stop starting large work, verify files and Git, update the documents, regenerate this prompt, and include it in the final response.

## PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL

Continuation prompts are permanent, never a one-time credit-exhaustion feature. Every future account must inherit this responsibility; no agent may remove, weaken, or omit it. Generate an updated self-contained prompt after every meaningful verified milestone, whenever the user asks to switch accounts, continue elsewhere, generate a handoff, or provide the next prompt, and before usage exhaustion. A milestone prompt does not require an account switch: continue development when usage permits.

At the conclusion of every completed user request or development phase, treat the ready-to-use next prompt as a required deliverable: refresh `NEXT_SESSION_PROMPT.md` from actual repository state before reporting completion. If the work is a meaningful verified milestone, commit and publish that refreshed checkpoint when GitHub is available.

Every new prompt must carry this protocol forward and tell the next account to generate another prompt. Never depend on previous conversation history. Always inspect the actual repository and Git state before continuing. At a user-requested handoff, stop starting new tasks, save/document the implementation, run feasible tests, and display the complete prompt in a copyable final-response block.

`NEXT_SESSION_PROMPT.md` must always be the latest ready-to-use prompt. Maintain it with `HANDOFF.md`, `PROJECT_STATUS.md`, `TASKS.md`, and `DEVELOPMENT_LOG.md` after each meaningful verified milestone. Every prompt must be self-contained and include: project objective; repository location/discovery; architecture; hardware; completed/incomplete work; branch, commit, and uncommitted state; files changed; dependencies; commands and test results; limitations; deployment state; exact next task; security restrictions; and this protocol. Never include passwords, API keys, tokens, or other secrets. This requirement is permanent and recursive across every account, model, and future development session.

## GitHub continuity and publishing

The official repository is `https://github.com/SamarthRamesha/personal-codex` (`origin`: `https://github.com/SamarthRamesha/personal-codex.git`), on `main`. Commit meaningful verified milestones and push to `origin/main` whenever remote access is available. Before publishing, verify remote state (`git fetch origin`, `git ls-remote origin refs/heads/main`), run relevant tests/checks, inspect Git status/diff, check that secrets, runtime databases, and temporary files are excluded, update checkpoints, and verify the resulting remote commit after pushing. Never force-push, erase unexpected remote history, publish secrets, or claim a push succeeded without verification. If unavailable, retain verified local commits and record them as unpushed. Every future prompt must carry these GitHub rules along with the permanent continuation protocol.

Publication was verified on 2026-11-01 at `2526fb4` (first push) and `d4ab9d4` (invocation milestone); the transport milestone commit was pushed next. Always re-inspect the remote before assuming synchronization.
