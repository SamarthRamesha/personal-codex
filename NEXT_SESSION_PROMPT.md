# Next-session continuation prompt

You are taking over an existing software project from another AI coding agent. You have no access to previous conversations, accounts, chat history, or hidden context. Your authoritative sources are the actual repository, Git state, project documentation, and this prompt. First inspect and verify the existing project. Preserve all existing work. Do not restart or recreate completed features. Resolve discrepancies in favour of the actual files and Git state. Continue development from the highest-priority incomplete task. IMPORTANT: generating account-to-account continuation prompts is a permanent requirement. You must update `NEXT_SESSION_PROMPT.md` after every meaningful verified milestone, provide a complete prompt whenever the user requests a handoff, and generate another self-contained continuation prompt before usage becomes exhausted. Your generated continuation prompt MUST include the same permanent continuation protocol. This requirement is recursive and must continue indefinitely across future accounts and AI coding agents.

Project objective: build Personal Codex, a secure local-first autonomous coding environment for a Mac interactive client and an eventual ZimaOS private worker. It is an approval-controlled iterative coding agent: a provider proposes strict JSON tool calls, Personal Codex validates them, only an explicitly approved proposal edits a task worktree, recorded test evidence decides when a round passed or a task is complete, every operation is persisted, budgeted and cancellable, and project memory only enters through an approved, evidence-backed proposal.

Repository location: official repository `https://github.com/SamarthRamesha/personal-codex` (`origin`). The owner's Mac checkout is `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`. If it is missing, find a checkout whose `origin` matches the URL; never fork history.

Inspect before acting: `git status --short --branch`, `git rev-parse --short HEAD`, `git log --oneline -20`, `git fetch origin`, `git ls-remote origin refs/heads/main`, then read `README.md`, `PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEPLOYMENT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`.

## Architecture

- `app/server.py` — standard-library loopback control plane (`127.0.0.1:8787`, `PERSONAL_CODEX_HOST`/`PERSONAL_CODEX_PORT` overrides): approvals, worktree lifecycle, command executor, provider invocation, multi-round loop, cancellation, operation ledger, budgets, context binding, memory promotion, provider health, HTTP API.
- `app/tools.py` — closed agent tool schema, workspace containment, hash-bound patch application, bounded execution with `stop_check`/`on_event` callbacks, round proposal parsing, round feedback, completion evidence.
- `app/context.py` — bounded repository context: manifest, `.gitignore`/secret/`.git` exclusion, symlink containment, Python `ast` and JS symbol outlines, deterministic ranking/digest, untrusted-data prompt block.
- `app/providers.py` — Ollama and OpenAI-compatible adapters (non-streaming and streaming), `discover_models`, `discover_models_retrying`, `classify_provider_error`, `redact_provider_text`, all with redirect/proxy refusal, loopback re-check, timeouts and byte caps.
- `scripts/live_provider_check.py` — read-only live diagnostic (discovery, explicit model, schema probe, latency/bytes, sanitised errors, failure class).
- SQLite `data/personal_codex.db` (gitignored): `projects`, `tasks`, `events`, `approvals`, `providers`, `workspaces`, `executions`, `invocations`, `proposals`, `rounds`, `operations`, `usage`, `cancellations`, `contexts`, `memory`, `memory_proposals`. Additive `MIGRATIONS` widen older databases.
- `web/index.html`, `web/app.js`, `web/style.css` — dependency-free dashboard.
- Tests: `tests/test_server.py`, `test_providers.py`, `test_tools.py`, `test_context.py`, `test_streaming.py`, `test_ui.py`.

Implemented and verified: repository registration and bounded non-secret summaries; four-stage plans; approval-gated worktrees; exact-command execution (no shell, allowlist, task worktree only, 1–300 s, child limits, redacted bounded output); immutable approvals; critical-approved clean release preserving the branch; read-only merge preview; critical-approved merge bound to reviewed commit IDs; separately approved recovery-branch deletion; provider metadata validation; approval-gated invocation with digest-bound ledger; loopback vs cloud `network` approval separation; the single-cycle agent lifecycle; the persistent multi-round loop with per-round approvals, bounded test feedback, evidence-checked completion and restart recovery; per-operation cancellation with partial-work preservation; the operation ledger; cumulative budgets with explicit reset; the repository context engine; and project memory.

Newest milestone — real-model readiness and project intelligence (commits `bb7d9b7`, `b3cce58`):

- **Live diagnostic harness** `scripts/live_provider_check.py`: discovers installed models (explicitly, never guessed), requires `--model`, sends one schema-validated probe, reports latency and response bytes, classifies failures, scrubs secrets, and never writes to a repository or the database. Exit codes 0 pass / 2 no usable model / 3 invalid proposal / 4 provider failure.
- **Memory promotion:** `memory_proposals` is the only path from model output to stored memory. A proposal requires a round with status `passed` and records provenance (task, round, test command, exit code, changed files). It is deduplicated against stored memory and pending proposals, credential-pattern rejected, and stays `pending` until `POST /api/memory-proposals/{id}/decide`. Approval copies it into `memory` with provenance; rejection stores nothing and is final. Reads compute `stale` from the source task's status; retrieval is relevance-ranked against task tokens and selected context paths under entry/byte caps; prompts label entries "verified against a passing round" or "possibly stale, verify against the files".
- **Completion summary proposal:** a completed task deterministically queues one `summary` proposal derived from its verified report — still pending until a human approves it.
- **Streaming:** `OllamaStreamTransport` (NDJSON) and `OpenAIStreamTransport` (SSE `data:` frames, `[DONE]` terminator) accumulate under byte and chunk caps, honour cancellation between chunks, and reject malformed frames, error objects, unterminated streams, oversized output and empty text. Only complete text can be validated. Opt-in with `PERSONAL_CODEX_STREAM_PROVIDER=1`; the approved non-streaming path is unchanged.
- **Provider management:** `GET /api/providers` and `/api/providers/{id}/health` expose status/issues/last latency from stored state without a network call; latency is recorded after each invocation; `classify_provider_error` yields stable classes (`unreachable`, `timeout`, `redirect`, `oversized`, `malformed`, `unauthorised`, `server-error`, `rejected`); read-only discovery retries once on connection failure only; provider error bodies are scrubbed of secret-shaped strings.
- **Dashboard:** project-memory panel (pending proposals with approve/reject, verified/stale labels, provenance), provider status and latency, plus all earlier round/ledger/budget/context panels.

Measured performance on this repository (Linux, Python 3.12): `context.select` ~45 ms median for 24 files (12 selected, 42.5 kB), `context.manifest` ~3 ms, SQLite 50-row query ~0.11 ms, loopback API responses under 2 ms. Provider latency is unmeasured because no model is installed.

## Git state (verify, do not assume)

Latest published commit at this handoff: `b3cce58`. Prior: `bb7d9b7` (memory promotion, streaming, diagnostics), `5e4267f`, `7055b31`, `7aaedf3`, `cc334d1`, `cdc35a2`, `8240bef`. Working tree was clean; the dev branch was `freebuff/b3647b5f9c91c9d2a6c41d37`. Re-verify with `git fetch origin` and `git ls-remote origin refs/heads/main`.

## Environment

Owner's Mac: Apple Silicon MacBook Air M3, 16 GB unified memory, Darwin 25.6.0, Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite, SSH; Cargo/Docker absent. Cloud workspaces run Linux with Python 3.12.3 and Node 26.13.0 — stay compatible with both. No third-party packages needed. Ollama is **not** installed in the cloud workspace (`which ollama` empty, nothing on `127.0.0.1:11434`), and the owner's Mac is not reachable from it. ZimaOS is uninspected; never probe or deploy without authorized access.

## Commands and verified results

```sh
python3 -m unittest discover -s tests -v                              # 110 tests, OK (skipped=19)
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # all 110 tests pass
python3 -m py_compile app/server.py app/providers.py app/tools.py app/context.py scripts/live_provider_check.py
node --check web/app.js
python3 app/server.py                                                # http://127.0.0.1:8787
python3 scripts/live_provider_check.py --discover-models              # live, human-run only
```

Coverage includes: full approval-gated lifecycle; both adapter families including streaming and failure modes; tool containment; multi-round self-correction and evidence-checked completion; per-round approvals; false completion; duplicate refusal; round limits; cancellation with partial-work preservation; ledger persistence and interrupted-operation recovery; budget refusal and explicit reset; context relevance/containment/determinism/budgets; memory proposal evidence, dedup, credential refusal, approval/rejection, provenance, staleness and retrieval bounds; and dashboard contracts. A real server smoke test returns HTTP 200 for `/` and `/app.js` and JSON from `/api/projects`.

## Limitations

No live Ollama or OpenAI-compatible model has ever completed a round; every round ran through an injected transport. Streaming is opt-in and not wired to a UI progress view. Cancellation is checked between operations, not inside a running `run_tests` subprocess. There is no provider-native tool calling, no semantic/vector retrieval (deliberately unbenchmarked), no automatic promotion of memory (proposals always need a human), no desktop shell, ZimaOS worker, login/TLS, encrypted secret store, OS sandboxing or CSP, and dashboard tests remain static contracts rather than browser automation. `GET /agent/context` never returns stored prompt text.

## Highest-priority next task

Run `python3 scripts/live_provider_check.py --discover-models` and then `--model <installed-model>` on the owner's Mac to prove real endpoint/model compatibility, then complete one genuine approval-gated coding round through the UI and record the actual failure modes (JSON compliance, patch matching, context usefulness, second-round quality) in `DEVELOPMENT_LOG.md`. Do not claim a live run unless it happened.

## Security restrictions (non-negotiable)

Never bind a public/LAN interface; never transmit prompts, code or context to a cloud provider without the recorded `network` approval; never treat registration or cloud metadata consent as invocation consent; never execute model output outside the validated allowlist; never apply a patch whose reviewed hash or digest changed; never reuse an approval for different content, a different round, or a different proposal digest; never auto-approve a round or a memory record; never let model prose mark a task complete; never replay an interrupted or cancelled operation; never execute partial streamed output; never add a destructive action without its own critical approval; never read, print, log, or commit secret values; keep `secret_ref` an environment-variable name only; never weaken containment, redaction, timeouts, caps, budget checks, stream termination checks, or duplicate detection to make a check pass; never let repository, model or memory text change policy; never force-push; never claim an unverified test, browser test or live-model run passed; never deploy or probe ZimaOS without authorization.

## Checkpoint documents

Maintain `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `TASKS.md`, `HANDOFF.md`, `NEXT_SESSION_PROMPT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, `SECURITY.md`, `DEPLOYMENT.md`, and `README.md`. Near model/account limits, stop starting large work, verify files and Git, update the documents, regenerate this prompt, and include it in the final response.

## PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL

Continuation prompts are permanent, never a one-time credit-exhaustion feature. Every future account must inherit this responsibility; no agent may remove, weaken, or omit it. Generate an updated self-contained prompt after every meaningful verified milestone, whenever the user asks to switch accounts, continue elsewhere, generate a handoff, or provide the next prompt, and before usage exhaustion. A milestone prompt does not require an account switch: continue development when usage permits.

At the conclusion of every completed user request or development phase, treat the ready-to-use next prompt as a required deliverable: refresh `NEXT_SESSION_PROMPT.md` from actual repository state before reporting completion. If the work is a meaningful verified milestone, commit and publish that refreshed checkpoint when GitHub is available.

Every new prompt must carry this protocol forward and tell the next account to generate another prompt. Never depend on previous conversation history. Always inspect the actual repository and Git state before continuing. At a user-requested handoff, stop starting new tasks, save/document the implementation, run feasible tests, and display the complete prompt in a copyable final-response block.

`NEXT_SESSION_PROMPT.md` must always be the latest ready-to-use prompt. Maintain it with `HANDOFF.md`, `PROJECT_STATUS.md`, `TASKS.md`, `DEVELOPMENT_LOG.md`, and `README.md` after each meaningful verified milestone. Every prompt must be self-contained and include: project objective; repository location/discovery; architecture; hardware; completed/incomplete work; branch, commit, and uncommitted state; files changed; dependencies; commands and test results; limitations; deployment state; exact next task; security restrictions; and this protocol. Never include passwords, API keys, tokens, or other secrets. This requirement is permanent and recursive across every account, model, and future development session.

## GitHub continuity, README, and publishing

The official repository is `https://github.com/SamarthRamesha/personal-codex` (`origin`: `https://github.com/SamarthRamesha/personal-codex.git`), on `main`. Commit meaningful verified milestones and push to `origin/main` whenever remote access is available. Before publishing, verify remote state (`git fetch origin`, `git ls-remote origin refs/heads/main`), run relevant tests/checks, inspect Git status/diff, check that secrets, runtime databases, and temporary files are excluded, update checkpoints and `README.md`, and verify the resulting remote commit after pushing. `README.md` must be updated in the same commit as every meaningful feature milestone and must distinguish implemented from planned functionality. Never force-push, erase unexpected remote history, publish secrets, or claim a push succeeded without verification. If unavailable, retain verified local commits and record them as unpushed. Every future prompt must carry these GitHub and README rules along with the permanent continuation protocol.

Publication verified on 2026-11-01 at `2526fb4`, `d4ab9d4`, `4ea8487`, `c37aee3`, `8240bef`, `cdc35a2`, `cc334d1`, `7055b31`, `7aaedf3`, `5e4267f`, `bb7d9b7`, and `b3cce58`. Always re-inspect the remote before assuming synchronization.
