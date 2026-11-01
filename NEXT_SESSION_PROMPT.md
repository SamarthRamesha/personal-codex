# Next-session continuation prompt

You are taking over an existing software project from another AI coding agent. You have no access to previous conversations, accounts, chat history, or hidden context. Your authoritative sources are the actual repository, Git state, project documentation, and this prompt. First inspect and verify the existing project. Preserve all existing work. Do not restart or recreate completed features. Resolve discrepancies in favour of the actual files and Git state. Continue development from the highest-priority incomplete task. IMPORTANT: generating account-to-account continuation prompts is a permanent requirement. You must update `NEXT_SESSION_PROMPT.md` after every meaningful verified milestone, provide a complete prompt whenever the user requests a handoff, and generate another self-contained continuation prompt before usage becomes exhausted. Your generated continuation prompt MUST include the same permanent continuation protocol. This requirement is recursive and must continue indefinitely across future accounts and AI coding agents.

Project objective: build Personal Codex, a secure local-first autonomous coding environment for a Mac interactive client and an eventual ZimaOS private worker.

Repository location: the official repository is `https://github.com/SamarthRamesha/personal-codex` (`origin` remote). The owner's working copy on the Mac is `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`. If that path does not exist, search for a checkout whose `origin` is the GitHub repository above. Do not create a new project or fork its history.

First inspect the repository and verify this prompt against actual files: `git status --short --branch`, `git rev-parse --short HEAD`, `git log --oneline -20`, then read `README.md`, `PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEVELOPMENT_LOG.md`, `CHANGELOG.md`, `DEPLOYMENT.md`. Do not recreate completed features. Resolve discrepancies in favour of the actual repository. Preserve every security requirement and keep checkpoints current.

## Current architecture

- Python standard-library loopback service: `app/server.py` (~440 lines), `ThreadingHTTPServer` bound to `127.0.0.1:8787` (`PERSONAL_CODEX_HOST`/`PERSONAL_CODEX_PORT` overrides).
- SQLite persistence at `data/personal_codex.db` (gitignored) with tables `projects`, `tasks`, `events`, `approvals`, `providers`, `workspaces`, `executions`, `invocations`.
- Static dashboard: `web/index.html`, `web/app.js`, `web/style.css` — no framework, no build step, no dependencies.
- Tests: `tests/test_server.py` (unit + opt-in HTTP lifecycle) and `tests/test_ui.py` (browser-free dashboard contract checks). Standard library only; no installed packages.

Implemented and verified: local repository registration; bounded non-secret repository summaries; four-stage planner/developer/testing/reviewer plans; approval-gated Git worktree creation; exact-command execution with no shell, development-tool allowlist, task-owned workspace only, 1–300 s timeout, child CPU/file/descriptor/address-space limits, 200 kB redacted output cap; immutable one-way approval decisions; critical-approval clean-worktree release that preserves the task branch as a recovery checkpoint; read-only merge previews with conflict reporting; critical-approved merge bound to reviewed source and target commit IDs (changed Git state invalidates the approval); separately approved recovery-branch deletion bound to the branch commit ID and gated on `merge-base --is-ancestor`; provider metadata validation for `ollama` and `openai-compatible` (absolute HTTP(S) endpoint, no embedded credentials, loopback unless `cloud_allowed: true`, `secret_ref` restricted to an environment-variable name, no secret read and no provider contact at registration).

Newest milestone (checkpoint commit `b0e25b7`, plus a following prompt-refresh commit): approval-gated provider invocation. `POST /api/tasks/{id}/provider-request` creates a pending approval whose canonical detail binds task, provider ID, endpoint, model, prompt SHA-256, and cloud flag; `POST /api/tasks/{id}/invoke` refuses unless an approved record with that exact detail exists. Loopback providers require approval kind `provider-invoke`; a provider registered with `cloud_allowed: true` requires a separate `network` approval, so metadata consent never implies transmission consent. The adapter receives only kind/endpoint/model/prompt — never the secret reference. The shipped `PROVIDER_TRANSPORT` is `unavailable_provider_transport`, which raises instead of opening a socket, so a prompt cannot leave the machine. Responses are bounded, redacted, stored in `invocations` with the prompt digest (the prompt itself is not stored there), listed at `GET /api/tasks/{id}/invocations`, and audited as an event. The dashboard now has provider invocation controls and a provider-response ledger, covered by `tests/test_ui.py` (scripted element IDs exist, every button is wired, every `/api/...` path in `app.js` is routed by `server.py`, all gated controls are present, only local assets load, no browser-stored secrets).

## Git state to verify, not assume

Branch in the last development workspace was `freebuff/b3647b5f9c91c9d2a6c41d37`; the owner's `main` should contain the same commits after publication. Commits of interest: `b0e25b7` (provider invocation lifecycle + dashboard tests), `f2fea40` (injected transport seam), `2ccf79f` (provider metadata validation), `7f8ae0b` (merge lifecycle), `2526fb4` (initial publication). Always run `git status --short --branch` and `git rev-parse --short HEAD` before acting; a committed prompt cannot know its own resulting hash. Working tree was clean at prompt generation. Remote state must be re-verified with `git fetch origin` and `git ls-remote origin refs/heads/main`; do not assume the remote still matches.

## Environment and hardware

Owner's Mac: Apple Silicon, Darwin 25.6.0, Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite and SSH available; Cargo and Docker not on PATH. No third-party packages are installed and none are required. The most recent cloud workspace ran Linux with Python 3.12.3 and Node 26.13.0; code must stay compatible with both. ZimaOS is uninspected: no endpoint, credentials, or authorized session were supplied. Do not probe or deploy to it.

## Commands and verified results (`b0e25b7`)

```sh
cd <repository root>
python3 -m unittest discover -s tests -v                              # 19 unit tests pass; listener test skipped
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # all 20 tests pass
python3 -m py_compile app/server.py                                   # passes
node --check web/app.js                                               # passes
python3 app/server.py                                                 # serves http://127.0.0.1:8787
```

The opt-in suite runs a disposable Git fixture and temporary SQLite database through: registration → task → provider guardrails → denied/approved workspace → denied/approved command → provider invocation denied/approved/invoked → changed-prompt rejection → invocation ledger → cloud `network` approval separation → clean release → merge preview → stale-merge-approval rejection → merge → branch deletion.

A real loopback smoke test in the last workspace additionally confirmed: `/api/health` OK; dashboard exposes the provider controls; invoke before approval returns 403; the approval detail carries endpoint, model, and prompt digest; invoking with an approval but the default transport returns `No approved provider transport is configured` and writes no ledger row; a cloud endpoint without consent returns 400. The server process was stopped afterwards and `data/personal_codex.db` was removed.

## Limitations

No real Ollama or OpenAI-compatible network client, no streaming, no tool-call execution, no agent engine that edits code autonomously, no native desktop shell, no server connector, no indexer/LSP, no encrypted secret storage, no login/auth, no TLS/remote protocol, no CSP headers, no OS sandboxing, no conflict-resolution tooling, and no browser-automation UI tests (the dashboard tests are static contract checks). Do not claim autonomous code modification, live model execution, or interactive UI verification beyond what has actually run.

Deployment state: nothing is deployed anywhere. The Mac app is run locally with `python3 app/server.py`. ZimaOS deployment is deferred pending authorized access.

## Highest-priority next task

Implement a real Ollama HTTP transport behind the existing injected seam, without weakening the approval boundary:

1. Keep `invoke_provider(provider, prompt, transport)` and the exact-detail approval check as-is; add the transport as an explicit opt-in module-level adapter that is selected only for `kind == "ollama"`.
2. Verify it first against a local stub HTTP server in tests (started on a loopback ephemeral port) so no live model is required; assert the outgoing request body, the bounded response handling, timeout/error mapping to a clear API error, and that non-loopback or cloud-consented providers cannot use it.
3. Never read the secret reference at registration; read an environment variable only inside the transport at call time if needed, and never log or persist it.
4. Then consider an OpenAI-compatible transport with the same rules, streaming later.

After that: agent-engine adapter with tool calls, project memory rebuild, and only then a Tauri shell. Add Playwright UI tests only where a browser runtime actually exists.

## Security restrictions (non-negotiable)

Never bind a public/LAN interface, never add remote push, never transmit code context or prompts to a cloud provider without the recorded `network` approval, never add a destructive action that is not separately critical-approved, never read, print, log, or commit secret values, never weaken approval binding, redaction, the command allowlist, workspace containment, or the immutable-decision rule to make a check pass. Keep `secret_ref` an environment-variable name only. Do not deploy or probe ZimaOS without authorized access. Do not include passwords, API keys, tokens, or other secrets in any document, prompt, or commit.

## Checkpoint documents

Continue recursively: maintain `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `TASKS.md`, `HANDOFF.md`, `NEXT_SESSION_PROMPT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, `SECURITY.md`, and `DEPLOYMENT.md`. If near model/account limits, stop starting large work, verify files and Git state, update those documents, regenerate this prompt from actual state, and include it directly in your final response.

## PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL

Continuation prompts are permanent, never a one-time credit-exhaustion feature. Every future account must inherit this responsibility; no agent may remove, weaken, or omit it. Generate an updated self-contained prompt after every meaningful verified milestone, whenever the user asks to switch accounts, continue elsewhere, generate a handoff, or provide the next prompt, and before usage exhaustion. A milestone prompt does not require an account switch: continue development when usage permits.

At the conclusion of every completed user request or development phase, treat the ready-to-use next prompt as a required deliverable: refresh `NEXT_SESSION_PROMPT.md` from actual repository state before reporting completion. If the work is a meaningful verified milestone, commit and publish that refreshed checkpoint when GitHub is available.

Every new prompt must carry this protocol forward and tell the next account to generate another prompt. Never depend on previous conversation history. Always inspect the actual repository and Git state before continuing. At a user-requested handoff, stop starting new tasks, save/document the implementation, run feasible tests, and display the complete prompt in a copyable final-response block.

`NEXT_SESSION_PROMPT.md` must always be the latest ready-to-use prompt. Maintain it with `HANDOFF.md`, `PROJECT_STATUS.md`, `TASKS.md`, and `DEVELOPMENT_LOG.md` after each meaningful verified milestone. Every prompt must be self-contained and include: project objective; repository location/discovery; architecture; hardware; completed/incomplete work; branch, commit, and uncommitted state; files changed; dependencies; commands and test results; limitations; deployment state; exact next task; security restrictions; and this protocol. Never include passwords, API keys, tokens, or other secrets. This requirement is permanent and recursive across every account, model, and future development session.

## GitHub continuity and publishing

The official repository is `https://github.com/SamarthRamesha/personal-codex` (`origin`: `https://github.com/SamarthRamesha/personal-codex.git`), on `main`. Commit meaningful verified milestones and push to `origin/main` whenever remote access is available. Before publishing, verify remote state (`git fetch origin`, `git ls-remote origin refs/heads/main`), run relevant tests/checks, inspect Git status/diff, check that secrets, runtime databases, and temporary files are excluded, update checkpoints, and verify the resulting remote commit (`git ls-remote` after pushing). Never force-push, erase unexpected remote history, publish secrets, or claim a push succeeded without verification. If unavailable, retain verified local commits and record them as unpushed. Every future prompt must carry these GitHub rules along with the permanent continuation protocol.

Initial publication was verified on 2026-11-01 at `2526fb4`. The latest milestone checkpoint is `b0e25b7`; re-verify remote state before assuming either is still the remote head.
