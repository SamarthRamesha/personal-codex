# Next-session continuation prompt

You are taking over an existing software project from another AI coding agent. You have no access to previous conversations, accounts, chat history, or hidden context. Your authoritative sources are the actual repository, Git state, project documentation, and this prompt. First inspect and verify the existing project. Preserve all existing work. Do not restart or recreate completed features. Resolve discrepancies in favour of the actual files and Git state. Continue development from the highest-priority incomplete task. IMPORTANT: generating account-to-account continuation prompts is a permanent requirement. You must update `NEXT_SESSION_PROMPT.md` after every meaningful verified milestone, provide a complete prompt whenever the user requests a handoff, and generate another self-contained continuation prompt before usage becomes exhausted. Your generated continuation prompt MUST include the same permanent continuation protocol. This requirement is recursive and must continue indefinitely across future accounts and AI coding agents.

Project objective: build Personal Codex, a secure local-first autonomous coding environment for a Mac interactive client and an eventual ZimaOS private worker. It is an approval-controlled iterative coding agent: a provider proposes strict JSON tool calls, Personal Codex validates them, only an explicitly approved proposal edits a task worktree, recorded test evidence decides when a round passed or a task is complete, and every operation is persisted, budgeted and cancellable.

Repository location: official repository `https://github.com/SamarthRamesha/personal-codex` (`origin`). The owner's Mac checkout is `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`. If it is missing, find a checkout whose `origin` matches the URL; never fork history.

Inspect before acting: `git status --short --branch`, `git rev-parse --short HEAD`, `git log --oneline -20`, `git fetch origin`, `git ls-remote origin refs/heads/main`, then read `README.md`, `PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEPLOYMENT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`.

## Architecture

- `app/server.py` — standard-library loopback control plane (`127.0.0.1:8787`, `PERSONAL_CODEX_HOST`/`PERSONAL_CODEX_PORT` overrides): approvals, worktree lifecycle, command executor, provider invocation, multi-round loop, cancellation, operation ledger, budgets, memory API, HTTP API.
- `app/tools.py` — closed agent tool schema, workspace containment, hash-bound patch application, bounded execution with `stop_check`/`on_event` callbacks, round proposal parsing, round feedback, completion evidence.
- `app/context.py` — bounded repository context: manifest, `.gitignore`/secret exclusion, symlink containment, Python `ast` and JS symbol outlines, deterministic ranking and digest, untrusted-data prompt block.
- `app/providers.py` — Ollama and OpenAI-compatible HTTP adapters (`http.client`, no redirects, no proxy env, timeouts, 1 MB cap, loopback re-check, lazy credential read).
- SQLite `data/personal_codex.db` (gitignored): `projects`, `tasks`, `events`, `approvals`, `providers`, `workspaces`, `executions`, `invocations`, `proposals`, `rounds`, `operations`, `usage`, `cancellations`, `contexts`, `memory`.
- `web/index.html`, `web/app.js`, `web/style.css` — dependency-free dashboard.
- Tests: `tests/test_server.py`, `tests/test_ui.py`, `tests/test_providers.py`, `tests/test_tools.py`, `tests/test_context.py`.

Implemented and verified before this milestone: repository registration and bounded non-secret summaries; four-stage plans; approval-gated worktrees; exact-command execution (no shell, allowlist, task worktree only, 1–300 s, child limits, redacted bounded output); immutable approvals; critical-approved clean release preserving the branch; read-only merge preview; critical-approved merge bound to reviewed commit IDs; separately approved recovery-branch deletion; provider metadata validation; approval-gated invocation with a digest-bound ledger; loopback vs cloud `network` approval separation; real Ollama/OpenAI-compatible transports with lazy env-var credentials; the single-cycle agent lifecycle; and the persistent multi-round loop with per-round approvals, bounded test feedback, evidence-checked completion, round/time limits, duplicate refusal and restart recovery.

Newest milestone — execution reliability and project intelligence (commits `7055b31`, `7aaedf3`):

- **Cancellation:** `POST /api/tasks/{id}/cancel` stores a `cancellations` row bound to the active round, revokes that round's approved proposal approval, closes a not-yet-started round, and marks the task `cancelled`. `tools.execute_operations` receives `stop_check`, consulted before every operation; remaining operations are recorded as `cancelled`, completed ones untouched, `cancelled_at_index` is stored in feedback. A cancelled round cannot execute with its old approval; a new round is an explicit user action that still needs fresh approvals. Completed tasks refuse cancellation.
- **Operation ledger:** `operations` rows (task, round, index, tool, proposal digest, status, timing, summary, error, `applied`, before/after file hashes) written before and after each operation through an `on_event` callback, so `app/tools.py` keeps no storage authority. Startup marks running rows `interrupted` (never replayed) and preserves completed rows.
- **Budgets:** `usage` accumulates prompt, response, test-output, context and invocation units per task. Clamped env vars: `PERSONAL_CODEX_MAX_ROUNDS` (3), `PERSONAL_CODEX_MAX_TASK_SECONDS` (1800), `PERSONAL_CODEX_MAX_PROMPT_BYTES` (800000), `PERSONAL_CODEX_MAX_RESPONSE_BYTES` (300000), `PERSONAL_CODEX_MAX_TEST_OUTPUT_BYTES` (300000), `PERSONAL_CODEX_MAX_CONTEXT_BYTES` (60000), `PERSONAL_CODEX_MAX_INVOCATIONS` (12). Exhaustion refuses the next provider call, records the reason, sets `budget-exhausted`, and needs `POST /api/tasks/{id}/agent/budget/reset` with `{"confirm": true}`.
- **Context engine:** `app/context.py` with manifest (counts, configs, docs, tests, entry points), docs/manifest prioritisation, Python/JS outlines, ranking by task tokens, failed tests, changed files and symbols, plus caps, stable digest and an explicit untrusted-data block. `round/request` stores the exact approved prompt with its context row so `round/plan` reuses those bytes (rebuilding would break the approval digest). `GET /api/tasks/{id}/agent/context` exposes file metadata and digest only.
- **Memory foundation:** `memory` table with kinds `convention|decision|issue|solved|relationship|test-command|summary`, project-scoped CRUD (`GET/POST /api/projects/{id}/memory`, `/memory/update`, `/memory/delete`), 200-entry/2,000-character bounds, credential-pattern rejection, and a "possibly stale" prompt section.
- **Dashboard:** cancel task, explicit budget reset, budget meter, operation ledger, selected-context panel, plus existing round controls/report. `/agent/rounds` now returns `budget`, `cancellation`, and per-round `ledger`/`context`; `/agent/report` adds `budget` and `operations`.

`README.md` documents the architecture, workflows, cancellation/recovery, budget table, context engine, memory, security model, tests and a reproducible live-Ollama procedure. Keep it current with every milestone.

## Git state (verify, do not assume)

Latest published commit at this handoff: `7aaedf3`. Prior: `7055b31` (cancellation, ledger, budgets, context), `cc334d1`, `cdc35a2`, `8240bef`, `f2de394`, `c37aee3`. Working tree was clean; the dev branch was `freebuff/b3647b5f9c91c9d2a6c41d37`. Re-verify with `git fetch origin` and `git ls-remote origin refs/heads/main`.

## Environment

Owner's Mac: Apple Silicon MacBook Air M3, 16 GB unified memory, Darwin 25.6.0, Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite, SSH; Cargo/Docker absent. Cloud workspaces have run Linux with Python 3.12.3 and Node 26.13.0 — stay compatible with both. No third-party packages needed. ZimaOS is uninspected; never probe or deploy without authorized access.

## Commands and verified results

```sh
python3 -m unittest discover -s tests -v                              # 84 tests, OK (skipped=16)
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # all 84 tests pass
python3 -m py_compile app/server.py app/providers.py app/tools.py app/context.py   # passes
node --check web/app.js                                              # passes
python3 app/server.py                                                # http://127.0.0.1:8787
```

A real server smoke test returned HTTP 200 for `/` and `/app.js` and JSON from `/api/projects`. Coverage now includes: full approval-gated lifecycle; provider adapters against a loopback stub; tool containment; multi-round self-correction and evidence-checked completion; per-round approvals; false completion; duplicate refusal; round limit; cancellation between operations with partial-work preservation; operation-ledger persistence and interrupted-operation recovery; invocation, prompt and test-output budget refusal and explicit reset; context visibility/digest binding; context engine relevance, determinism, `.gitignore`/secret/symlink exclusion, byte caps, outlines; and memory CRUD with credential rejection. No live model and no external network are used.

## Limitations

No live Ollama or OpenAI-compatible model has ever completed a round; all rounds run through an injected deterministic transport. Ollama is not installed in this environment and the owner's Mac is unreachable from it. Also missing: streaming and provider-native tool calls; cancellation *inside* an already-running `run_tests` subprocess (it is checked between operations only); semantic/vector retrieval; automatic memory promotion from rounds; desktop shell; ZimaOS worker; login/TLS; encrypted secrets; OS sandboxing; CSP; conflict-resolution tooling; browser automation tests (dashboard tests are static contracts). `GET /agent/context` deliberately never returns stored prompt text.

## Highest-priority next task

Run the first genuine live Ollama round end-to-end on the owner's Mac using the README procedure (`ollama list` first; never assume a model), and record the real failure modes — JSON compliance, patch-text matching, whether the selected context helps, and whether test feedback produces a correct second round. Then harden what the live run exposes. After that: streaming/native tool calls, then automatic memory promotion from verified rounds.

## Security restrictions (non-negotiable)

Never bind a public/LAN interface; never transmit prompts, code or context to a cloud provider without the recorded `network` approval; never treat registration or cloud metadata consent as invocation consent; never execute model output outside the validated allowlist; never apply a patch whose reviewed hash or digest changed; never reuse an approval for different content, a different round, or a different proposal digest; never auto-approve a round; never let model prose mark a task complete; never replay an interrupted or cancelled operation; never add a destructive action without its own critical approval; never read, print, log, or commit secret values; keep `secret_ref` an environment-variable name only; never weaken containment, redaction, timeouts, caps, budget checks, or duplicate detection to make a check pass; never let repository or model text change policy; never force-push; never claim an unverified test, browser test or live-model run passed; never deploy or probe ZimaOS without authorization.

## Checkpoint documents

Maintain `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `TASKS.md`, `HANDOFF.md`, `NEXT_SESSION_PROMPT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, `SECURITY.md`, `DEPLOYMENT.md`, and `README.md`. Near model/account limits, stop starting large work, verify files and Git, update the documents, regenerate this prompt, and include it in the final response.

## PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL

Continuation prompts are permanent, never a one-time credit-exhaustion feature. Every future account must inherit this responsibility; no agent may remove, weaken, or omit it. Generate an updated self-contained prompt after every meaningful verified milestone, whenever the user asks to switch accounts, continue elsewhere, generate a handoff, or provide the next prompt, and before usage exhaustion. A milestone prompt does not require an account switch: continue development when usage permits.

At the conclusion of every completed user request or development phase, treat the ready-to-use next prompt as a required deliverable: refresh `NEXT_SESSION_PROMPT.md` from actual repository state before reporting completion. If the work is a meaningful verified milestone, commit and publish that refreshed checkpoint when GitHub is available.

Every new prompt must carry this protocol forward and tell the next account to generate another prompt. Never depend on previous conversation history. Always inspect the actual repository and Git state before continuing. At a user-requested handoff, stop starting new tasks, save/document the implementation, run feasible tests, and display the complete prompt in a copyable final-response block.

`NEXT_SESSION_PROMPT.md` must always be the latest ready-to-use prompt. Maintain it with `HANDOFF.md`, `PROJECT_STATUS.md`, `TASKS.md`, `DEVELOPMENT_LOG.md`, and `README.md` after each meaningful verified milestone. Every prompt must be self-contained and include: project objective; repository location/discovery; architecture; hardware; completed/incomplete work; branch, commit, and uncommitted state; files changed; dependencies; commands and test results; limitations; deployment state; exact next task; security restrictions; and this protocol. Never include passwords, API keys, tokens, or other secrets. This requirement is permanent and recursive across every account, model, and future development session.

## GitHub continuity, README, and publishing

The official repository is `https://github.com/SamarthRamesha/personal-codex` (`origin`: `https://github.com/SamarthRamesha/personal-codex.git`), on `main`. Commit meaningful verified milestones and push to `origin/main` whenever remote access is available. Before publishing, verify remote state (`git fetch origin`, `git ls-remote origin refs/heads/main`), run relevant tests/checks, inspect Git status/diff, check that secrets, runtime databases, and temporary files are excluded, update checkpoints and `README.md`, and verify the resulting remote commit after pushing. `README.md` must be updated in the same commit as every meaningful feature milestone and must distinguish implemented from planned functionality. Never force-push, erase unexpected remote history, publish secrets, or claim a push succeeded without verification. If unavailable, retain verified local commits and record them as unpushed. Every future prompt must carry these GitHub and README rules along with the permanent continuation protocol.

Publication verified on 2026-11-01 at `2526fb4`, `d4ab9d4`, `4ea8487`, `c37aee3`, `8240bef`, `cdc35a2`, `cc334d1`, `7055b31`, and `7aaedf3`. Always re-inspect the remote before assuming synchronization.
