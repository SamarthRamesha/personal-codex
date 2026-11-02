# Next-session continuation prompt

You are taking over an existing software project from another AI coding agent. You have no access to previous conversations, accounts, chat history, or hidden context. Your authoritative sources are the actual repository, Git state, project documentation, and this prompt. First inspect and verify the existing project. Preserve all existing work. Do not restart or recreate completed features. Resolve discrepancies in favour of the actual files and Git state. Continue development from the highest-priority incomplete task. IMPORTANT: generating account-to-account continuation prompts is a permanent requirement. You must update `NEXT_SESSION_PROMPT.md` after every meaningful verified milestone, provide a complete prompt whenever the user requests a handoff, and generate another self-contained continuation prompt before usage becomes exhausted. Your generated continuation prompt MUST include the same permanent continuation protocol. This requirement is recursive and must continue indefinitely across future accounts and AI coding agents.

## Objective

Personal Codex is a local-first, approval-controlled autonomous coding environment for a Mac interactive client and an eventual ZimaOS private worker. A provider proposes strict JSON tool calls; Personal Codex validates them; only an explicitly approved proposal edits a task worktree; recorded test evidence decides whether a round passed or a task is complete; every operation is persisted, budgeted and cancellable; project memory only enters through an approved, evidence-backed proposal. The long-term product goal is an installable ChatGPT-style macOS desktop app (Tauri + React + TypeScript over the existing Python/SQLite control plane), a self-maintaining home-server worker, and default-deny outbound networking with local inference only.

## Repository and reconciliation

- Official repository: `https://github.com/SamarthRamesha/personal-codex` (`origin`), branch `main`.
- Owner's Mac checkout: `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`.
- The owner's Mac previously reported local `f2fea40` while `origin/main` had advanced (then `e9b0ee5`). That checkout is simply behind: fast-forward it (`git fetch origin && git merge --ff-only origin/main`). Never reset, rebase or force-push it, and never commit the untracked `personal-codex-diagnostic.txt`.
- Inspect before acting: `git status --short --branch`, `git rev-parse --short HEAD`, `git log --oneline -15`, `git fetch origin`, `git ls-remote origin refs/heads/main`, then read `README.md`, `PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEPLOYMENT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`.

## Architecture

- `app/server.py` — standard-library loopback control plane (`127.0.0.1:8787`, `PERSONAL_CODEX_HOST`/`PERSONAL_CODEX_PORT`): approvals, worktrees, command executor, provider invocation, multi-round loop, cancellation (including subprocess termination), operation ledger, budgets, context binding, memory promotion, provider health, SSE event stream, diff review, repository search, HTTP API.
- `app/tools.py` — closed agent tool schema, workspace containment, hash-bound patches, bounded execution with `stop_check`/`on_event`, round proposal parsing, `review_operations` (diff + digest stale detection), round feedback, completion evidence.
- `app/context.py` — bounded context selection, manifest, `.gitignore`/secret/`.git` exclusion, symlink containment, Python `ast`/JS outlines, deterministic ranking and digest, untrusted prompt block, and `search()`.
- `app/providers.py` — Ollama and OpenAI-compatible adapters (non-streaming and streaming), `discover_models`, `discover_models_retrying`, `classify_provider_error`, `redact_provider_text`, redirect/proxy refusal, loopback re-check, timeouts and byte caps.
- `scripts/live_provider_check.py` — read-only live diagnostic (discovery, explicit model, schema probe, latency/bytes, sanitised errors, exit 0/2/3/4).
- `web/index.html`, `web/app.js`, `web/style.css` — dependency-free dashboard: approvals, rounds, ledger, budgets, context, memory, provider status, diff review, repository search, live SSE activity.
- SQLite `data/personal_codex.db` (gitignored): `projects`, `tasks`, `events`, `approvals`, `providers`, `workspaces`, `executions`, `invocations`, `proposals`, `rounds`, `operations`, `usage`, `cancellations`, `contexts`, `memory`, `memory_proposals`. Additive `MIGRATIONS` widen older databases.
- Tests: `test_server.py`, `test_providers.py`, `test_tools.py`, `test_context.py`, `test_streaming.py`, `test_interaction.py`, `test_ui.py`.

## Completed and verified

Repository registration; bounded non-secret summaries; four-stage plans; approval-gated worktrees; exact-command execution (no shell, allowlist, task worktree only, 1–300 s, child limits, redacted bounded output); immutable approvals; clean release with a recovery branch; read-only merge preview; critical-approved merge bound to reviewed commit IDs; separately approved branch deletion; provider metadata validation; approval-gated invocation with a digest-bound ledger; loopback vs cloud `network` approval separation; single-cycle agent lifecycle; persistent multi-round loop with per-round approvals, bounded test feedback, evidence-checked completion and restart recovery; per-operation cancellation; operation ledger; cumulative budgets with explicit reset; bounded context engine; project memory with evidence-backed promotion (dedupe, credential refusal, provenance, staleness, relevance-ranked retrieval, completion summary proposal that stays pending); bounded streaming for both provider families; failure classification with a single read-only discovery retry; provider health/latency from stored state; read-only live diagnostic harness.

Milestone 6 (commit `faffca7`) closed the interactive gaps:

- Cancellation reaches the running subprocess: `execute_in_workspace(..., stop_check=)` polls every 200 ms, SIGTERMs the process group, escalates to SIGKILL after 1.5 s, preserves partial output, and returns exit code 130 with `cancelled: true`. The tool layer records a stopped command as `cancelled` (not a failed test), and remaining operations never start.
- `GET /api/tasks/{id}/events/stream` — Server-Sent Events over the persisted `events` table, ids are SQLite rowids, `Last-Event-ID`/`?after=` resume without replay, bounded to 500 events / 120 s, keep-alive comments, clean close on a dead client.
- `GET /api/tasks/{id}/agent/diff` — unified diff per pending `apply_patch`, bound digest, current digest, occurrence count, `stale` flag; the dashboard disables execution when stale or the digest no longer matches.
- `GET /api/projects/{id}/search?q=&limit=` — case-insensitive, `.gitignore`-aware, never returns secret-named files, symlinks or generated directories; capped at 50 matches and 220 characters per line.
- Every response sends `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Cache-Control: no-store`, and a CSP (`default-src 'self'` for the dashboard with no inline script/style, `default-src 'none'` for JSON).

## Git state (verify, do not assume)

Latest published commit at this handoff: `faffca7` (on top of `e9b0ee5`, `b3cce58`, `bb7d9b7`, `5e4267f`, `7055b31`, `7aaedf3`, `cc334d1`, `cdc35a2`, `8240bef`). Working tree was clean; the dev branch was `freebuff/b3647b5f9c91c9d2a6c41d37`. Re-verify with `git fetch origin` and `git ls-remote origin refs/heads/main`.

## Environment

Owner's Mac: Apple Silicon MacBook Air M3, 16 GB unified memory, macOS, Python 3.13.9, Node 24.22.1, npm 11.19.1, Git 2.50.1, SQLite. Cargo/Rust was **not** on PATH, so a Tauri build has never been attempted. Cloud workspaces run Linux with Python 3.12.3 and Node 26.13.0. No third-party Python packages. Ollama is not installed in the cloud workspace and nothing listens on `127.0.0.1:11434`; the owner's Mac also reported `ollama: command not found`. ZimaOS connection details have never been supplied — do not probe or deploy.

## Commands and verified results

```sh
python3 -m unittest discover -s tests -v                              # 126 tests, OK (skipped=19)
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # all 126 tests pass
python3 -m py_compile app/server.py app/providers.py app/tools.py app/context.py scripts/live_provider_check.py
node --check web/app.js
python3 app/server.py                                                # http://127.0.0.1:8787
python3 scripts/live_provider_check.py --discover-models              # live, human-run on the Mac
```

Coverage: approval-gated lifecycle; both adapter families including streaming and failure modes; tool containment; multi-round self-correction; per-round approvals; false completion; duplicate refusal; round limits; cancellation between operations and now mid-command (terminal process-group stop, partial output, exit 130, no lingering child); ledger persistence and interrupted recovery; budgets; context relevance/containment/determinism; memory proposal evidence, dedup, credential refusal, approval/rejection, provenance, staleness, retrieval bounds; diff/hash/stale semantics; search containment; stream resumption; security headers; dashboard contracts. A loopback smoke test returns 200 for `/` and `/app.js` and JSON from `/api/health`.

## Limitations (state these honestly, never as passes)

No live Ollama or OpenAI-compatible model has ever completed a round; every round used an injected transport. Streaming is opt-in (`PERSONAL_CODEX_STREAM_PROVIDER=1`) and there is no token-by-token UI rendering (activity is streamed, provider text is not). No browser automation in this environment: dashboard tests are static contracts plus HTTP tests, so browser and packaged-app checks are pending. No native desktop shell, no Tauri project, no ZimaOS worker, no login/TLS/remote protocol, no encrypted secret store, no OS-level egress enforcement or sandbox, no telemetry-free packaging verification, no model catalogue/update or benchmark subsystem, no self-maintenance scheduler/backups/restore tests, and no provider-native tool calling.

## Highest-priority next tasks, in order

1. **Live model proof (owner's Mac).** Install Ollama, pull a model, then `python3 scripts/live_provider_check.py --discover-models` and `--model <exact-model>`. Then complete one genuine approval-gated round through the UI on a disposable repository and record the real failure modes (JSON compliance, patch matching, context usefulness, second-round quality) in `DEVELOPMENT_LOG.md`. Never claim a live run that did not happen.
2. **Desktop foundation (Phase 4).** Check `cargo --version`; if Rust is absent, document the blocker and prepare the app without claiming it builds. Build a Tauri + React + TypeScript shell that supervises the existing Python backend (single instance, crash recovery, clean shutdown, portable path resolution), keeping the backend authoritative for approvals. Do not remove the working dashboard until the shell has parity.
3. **Stable app APIs before UI breadth.** Conversations/messages, streaming provider output, agent activity, diff review, approvals, model selection, attachments, cancellation, memory, health. Version and test them.
4. **Self-maintenance (Phase 5).** Health history, bounded recovery with backoff and idempotency, SQLite backups with integrity checks and a tested restore into a temporary directory, log rotation, storage thresholds, maintenance dashboard, and a maintenance agent that may only propose patches through the existing approval flow.
5. **Privacy enforcement (Phase 6).** Default-deny application egress with explicit loopback/home-server allowlisting, verified fail-closed behaviour at the OS boundary where possible, no cloud fallback, no telemetry. Document exactly which enforcement is tested and which is not.
6. **Model lifecycle (Phase 7)** — trusted import manifest, hashes, licence/compatibility/storage checks, staged install, benchmark and rollback, no downloads of arbitrary weights and no fine-tuning on private data.
7. **ZimaOS worker (Phase 8)** only after explicit authorization and connection details; mutually authenticated, encrypted, least privilege, same approval policy.

## Security and privacy restrictions (non-negotiable)

Never bind a public/LAN interface. Never transmit prompts, code, context, memory or logs to a cloud provider without a recorded `network` approval, and never add cloud inference as an automatic fallback. Default-deny runtime egress apart from loopback and the owner's authenticated worker. Never execute model output outside the validated allowlist. Never apply a patch whose reviewed hash or digest changed. Never reuse an approval for different content, a different round, or a different proposal digest. Never auto-approve a round or a memory record. Never let model prose mark a task complete. Never replay an interrupted or cancelled operation; never execute partial streamed output. Never add a destructive action without its own critical approval. Never read, print, log or commit secret values; keep `secret_ref` an environment-variable name only. Never weaken containment, redaction, timeouts, caps, budget checks, stream termination, duplicate detection or CSP to make a check pass. Never force-push or overwrite unexpected remote history. Never claim an unverified test, browser test, live-model run or native build passed. Never probe or deploy ZimaOS without authorization. GitHub publishing is a developer workflow: never send application data, prompts, databases, credentials or diagnostic dumps to GitHub.

## Checkpoint documents

Maintain `README.md`, `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `TASKS.md`, `HANDOFF.md`, `NEXT_SESSION_PROMPT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, `SECURITY.md`, `DEPLOYMENT.md`. `README.md` must separate implemented, tested, partially implemented, planned and blocked. Commit and push each meaningful verified milestone, verify the resulting remote commit, and record unpushed work if GitHub is unavailable.

## PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL

Continuation prompts are permanent, never a one-time credit-exhaustion feature. Every future account must inherit this responsibility; no agent may remove, weaken, or omit it. Generate an updated self-contained prompt after every meaningful verified milestone, whenever the user asks to switch accounts, continue elsewhere, generate a handoff, or provide the next prompt, and before usage exhaustion. A milestone prompt does not require an account switch: continue development when usage permits.

At the conclusion of every completed user request or development phase, treat the ready-to-use next prompt as a required deliverable: refresh `NEXT_SESSION_PROMPT.md` from actual repository state before reporting completion. If the work is a meaningful verified milestone, commit and publish that refreshed checkpoint when GitHub is available.

Every new prompt must carry this protocol forward and tell the next account to generate another prompt. Never depend on previous conversation history. Always inspect the actual repository and Git state before continuing. At a user-requested handoff, stop starting new tasks, save/document the implementation, run feasible tests, and display the complete prompt in a copyable final-response block.

`NEXT_SESSION_PROMPT.md` must always be the latest ready-to-use prompt. Every prompt must be self-contained and include: project objective; repository location and discovery; architecture; hardware; completed and incomplete work; branch, commit and uncommitted state; files changed; dependencies; commands and test results; limitations; deployment state; exact next task; security and privacy restrictions; GitHub and README rules; and this protocol. Never include passwords, API keys, tokens, or other secrets. This requirement is permanent and recursive across every account, model, and future development session.

Publication verified on 2026-11-01/02 at `2526fb4`, `d4ab9d4`, `4ea8487`, `c37aee3`, `8240bef`, `cdc35a2`, `cc334d1`, `7055b31`, `7aaedf3`, `5e4267f`, `bb7d9b7`, `b3cce58`, `e9b0ee5`, `faffca7`. Always re-inspect the remote before assuming synchronization.
