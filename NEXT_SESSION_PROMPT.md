# Next-session continuation prompt

You are taking over an existing software project from another AI coding agent. You have no access to previous conversations, accounts, chat history, or hidden context. Your authoritative sources are the actual repository, Git state, project documentation, and this prompt. First inspect and verify the existing project. Preserve all existing work. Do not restart or recreate completed features. Resolve discrepancies in favour of the actual files and Git state. Continue development from the highest-priority incomplete task. IMPORTANT: generating account-to-account continuation prompts is a permanent requirement. You must update `NEXT_SESSION_PROMPT.md` after every meaningful verified milestone, provide a complete prompt whenever the user requests a handoff, and generate another self-contained continuation prompt before usage becomes exhausted. Your generated continuation prompt MUST include the same permanent continuation protocol. This requirement is recursive and must continue indefinitely across future accounts and AI coding agents.

Project objective: build Personal Codex, a secure local-first autonomous coding environment for a Mac interactive client and an eventual ZimaOS private worker. It is an approval-controlled iterative coding agent: a provider proposes strict JSON tool calls, Personal Codex validates them, only an explicitly approved proposal edits a task worktree, and recorded test evidence — not model prose — decides when a round passed or a task is complete.

Repository location: official repository `https://github.com/SamarthRamesha/personal-codex` (`origin`). The owner's Mac checkout is `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`. If it is missing, find a checkout whose `origin` matches the URL; never fork history.

Inspect before acting: `git status --short --branch`, `git rev-parse --short HEAD`, `git log --oneline -20`, `git fetch origin`, `git ls-remote origin refs/heads/main`, then read `README.md`, `PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEPLOYMENT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`.

## Architecture

- `app/server.py` — standard-library loopback control plane (`127.0.0.1:8787`, `PERSONAL_CODEX_HOST`/`PERSONAL_CODEX_PORT` overrides), approvals, worktree lifecycle, command executor, provider invocation, multi-round loop, HTTP API.
- `app/tools.py` — closed agent tool schema, workspace containment, hash-bound patch application, bounded execution, round proposal parsing, round feedback, completion evidence.
- `app/providers.py` — Ollama and OpenAI-compatible HTTP adapters (`http.client`, no redirects, no proxy env, timeouts, 1 MB cap, loopback re-check, lazy credential read).
- SQLite `data/personal_codex.db` (gitignored): `projects`, `tasks`, `events`, `approvals`, `providers`, `workspaces`, `executions`, `invocations`, `proposals`, `rounds`.
- `web/index.html`, `web/app.js`, `web/style.css` — dependency-free dashboard.
- Tests: `tests/test_server.py`, `tests/test_ui.py`, `tests/test_providers.py`, `tests/test_tools.py`.

Implemented and verified: repository registration; non-secret bounded summaries; four-stage plans; approval-gated worktrees; exact-command execution (no shell, allowlist, task worktree only, 1–300 s, child limits, redacted bounded output); immutable approvals; critical-approved clean release preserving the branch; read-only merge preview; critical-approved merge bound to reviewed commit IDs; separately approved recovery-branch deletion; provider metadata validation; approval-gated provider invocation with a digest-bound ledger; loopback vs cloud `network` approval separation; real Ollama and OpenAI-compatible transports with lazy env-var credentials; a single-cycle agent proposal lifecycle (`request` → `plan` → `execute`, digest and hash bound, single use).

Newest milestone — persistent multi-round loop (commits `8240bef` and `cdc35a2`):

- `rounds` table (task, round number, provider, model, prompt digest, proposal id/digest, approval id, status, summary, operations, results, test result, error, timestamps), deliberately separate from `proposals`.
- API: `POST /api/tasks/{id}/agent/round/request` (deterministic prompt over task, 60-path listing, bounded history → `provider-invoke` approval bound to the round and prompt digest), `POST .../round/plan` (requires that approval, one adapter call, refuses byte-identical repeated responses, parses `{"summary","status","operations"}`, binds hashes, queues an `agent-round-proposal` approval bound to round/workspace branch+path/proposal digest/prompt digest), `POST .../round/execute` (recomputes digest, re-checks workspace and file hashes, atomically claims round + proposal, executes tools, records feedback), `POST .../round/cancel` (invalidates the pending proposal), `GET .../agent/rounds` (limits + full history), `GET .../agent/report` (changed files, test runs, diff summary).
- Feedback loop: `tools.round_feedback` records test command, exit code, redacted 2 000-character output tail, failed test names (`FAIL:`/`ERROR:` lines), changed files, and errors; `build_round_prompt` embeds that plus prior summaries in the next prompt.
- Evidence-based statuses: hard non-`run_tests` failure → `failed`; zero-exit test command → `passed`; otherwise `failed-checks`. Model statuses are strictly `continue|complete|blocked|failed`. `complete` is accepted only when `tools.completion_evidence` proves an executed round, a zero-exit test command, an approved file change, and a passing latest executed round; otherwise the claim is stored as `rejected-completion` and the workspace is untouched.
- Limits: `PERSONAL_CODEX_MAX_ROUNDS` (1–10, default 3), 1 800 s per task, 8 operations per round, one provider call per round, adapter response cap. Duplicate responses and duplicate proposal digests are refused.
- Restart recovery: `Store.recover_interrupted` marks rounds left `executing` as `interrupted`, closes the proposal, writes an event, and moves an `iterating` task to `needs-another-round`.
- Dashboard: round controls (request/propose/execute/cancel), round count/limit/elapsed, per-round status with test exit codes and failed test names, errors, and a final report panel; action buttons ignore clicks while a request is in flight.

`README.md` was rewritten as the full project guide (objective, architecture, quick start, round lifecycle, approvals, security model, tests, roadmap) and must be updated with every meaningful milestone.

## Git state (verify, do not assume)

Latest published commit at this handoff: `cdc35a2` (restart recovery + duplicate-click guard). Prior: `8240bef` (persistent multi-round execution), `f2de394` (prior continuation-prompt refresh), `c37aee3` (agent tool execution), `4ea8487` (transport checkpoint). Working tree was clean; the dev branch was `freebuff/b3647b5f9c91c9d2a6c41d37`. Re-verify with `git fetch origin` and `git ls-remote origin refs/heads/main`.

## Environment

Owner's Mac: Apple Silicon, Darwin 25.6.0, Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite, SSH; Cargo/Docker absent. Cloud workspaces have run Linux with Python 3.12.3 and Node 26.13.0 — stay compatible with both. No third-party packages needed. ZimaOS is uninspected; never probe or deploy without authorized access.

## Commands and verified results

```sh
python3 -m unittest discover -s tests -v                              # 66 tests, OK (skipped=9)
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # all 66 tests pass
python3 -m py_compile app/server.py app/providers.py app/tools.py     # passes
node --check web/app.js                                              # passes
python3 app/server.py                                                # http://127.0.0.1:8787
```

Coverage includes the full approval-gated lifecycle (workspace, command, release, merge, branch deletion), provider guardrails and adapter failure modes against a loopback stub server, tool schema and containment rejections, an opt-in HTTP agent lifecycle, and the multi-round loop: a failing round followed by a corrected passing round and an evidence-checked completion, per-round approvals, false-completion rejection, duplicate-response refusal, the round limit, cancellation, and restart recovery. No live model or external network is used anywhere.

## Limitations

Every round so far was driven by an injected deterministic transport — no live Ollama or OpenAI-compatible model has ever completed a round, so do not claim verified autonomous coding by a real model. Also missing: streaming and provider-native tool calls; project memory/indexer (so context is a 60-path listing plus history, not semantic retrieval); a cancellation check between tool operations inside a long round and partial-result checkpoints; cumulative model-output budget beyond the per-round adapter cap; desktop shell, ZimaOS worker, login/TLS, encrypted secrets, OS sandboxing, CSP, conflict-resolution tooling; dashboard tests are static contracts, not browser automation.

## Highest-priority next task

Run the first real Ollama round end-to-end on the owner's Mac: register a provider, execute a two-round task through the live loop, and record the actual failure modes observed (prompt assembly, JSON compliance, patch text matching, test feedback usefulness). Then harden what a live model exposes: per-operation cancellation checks and partial-result persistence, a cumulative-output budget, and a project-memory selector (manifests, docs, symbol outline) that keeps prompts bounded. After that: streaming, native tool calls, the Tauri shell.

## Security restrictions (non-negotiable)

Never bind a public/LAN interface; never transmit prompts or code to a cloud provider without the recorded `network` approval; never treat registration or cloud metadata consent as invocation consent; never execute model output outside the validated allowlist; never apply a patch whose reviewed hash or digest changed; never reuse an approval for different content, a different round, or a different proposal digest; never auto-approve a round; never let model prose mark a task complete; never add a destructive action without its own critical approval; never read, print, log, or commit secret values; keep `secret_ref` an environment-variable name only; never weaken containment, redaction, timeouts, caps, or duplicate detection to make a check pass; never force-push; never claim an unverified test, browser test, or live-model run passed; never deploy or probe ZimaOS without authorization.

## Checkpoint documents

Maintain `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `TASKS.md`, `HANDOFF.md`, `NEXT_SESSION_PROMPT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, `SECURITY.md`, `DEPLOYMENT.md`, and `README.md`. Near model/account limits, stop starting large work, verify files and Git, update the documents, regenerate this prompt, and include it in the final response.

## PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL

Continuation prompts are permanent, never a one-time credit-exhaustion feature. Every future account must inherit this responsibility; no agent may remove, weaken, or omit it. Generate an updated self-contained prompt after every meaningful verified milestone, whenever the user asks to switch accounts, continue elsewhere, generate a handoff, or provide the next prompt, and before usage exhaustion. A milestone prompt does not require an account switch: continue development when usage permits.

At the conclusion of every completed user request or development phase, treat the ready-to-use next prompt as a required deliverable: refresh `NEXT_SESSION_PROMPT.md` from actual repository state before reporting completion. If the work is a meaningful verified milestone, commit and publish that refreshed checkpoint when GitHub is available.

Every new prompt must carry this protocol forward and tell the next account to generate another prompt. Never depend on previous conversation history. Always inspect the actual repository and Git state before continuing. At a user-requested handoff, stop starting new tasks, save/document the implementation, run feasible tests, and display the complete prompt in a copyable final-response block.

`NEXT_SESSION_PROMPT.md` must always be the latest ready-to-use prompt. Maintain it with `HANDOFF.md`, `PROJECT_STATUS.md`, `TASKS.md`, `DEVELOPMENT_LOG.md`, and `README.md` after each meaningful verified milestone. Every prompt must be self-contained and include: project objective; repository location/discovery; architecture; hardware; completed/incomplete work; branch, commit, and uncommitted state; files changed; dependencies; commands and test results; limitations; deployment state; exact next task; security restrictions; and this protocol. Never include passwords, API keys, tokens, or other secrets. This requirement is permanent and recursive across every account, model, and future development session.

## GitHub continuity, README, and publishing

The official repository is `https://github.com/SamarthRamesha/personal-codex` (`origin`: `https://github.com/SamarthRamesha/personal-codex.git`), on `main`. Commit meaningful verified milestones and push to `origin/main` whenever remote access is available. Before publishing, verify remote state (`git fetch origin`, `git ls-remote origin refs/heads/main`), run relevant tests/checks, inspect Git status/diff, check that secrets, runtime databases, and temporary files are excluded, update checkpoints and `README.md`, and verify the resulting remote commit after pushing. `README.md` must be updated in the same commit as every meaningful feature milestone and must distinguish implemented from planned functionality. Never force-push, erase unexpected remote history, publish secrets, or claim a push succeeded without verification. If unavailable, retain verified local commits and record them as unpushed. Every future prompt must carry these GitHub and README rules along with the permanent continuation protocol.

Publication verified on 2026-11-01 at `2526fb4`, `d4ab9d4`, `4ea8487`, `c37aee3`, `8240bef`, and `cdc35a2`. Always re-inspect the remote before assuming synchronization.
