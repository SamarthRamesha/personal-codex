# Personal Codex

Personal Codex is a private, local-first AI coding control plane for macOS. It connects a registered Git repository, a local or explicitly consented model provider, and a task workspace where an agent can propose — and you can approve — small, auditable code changes.

Nothing is autonomous by default. A model may *propose* file edits and test commands as strict JSON; Personal Codex validates them, shows you the exact digest, and only applies them to an isolated Git worktree after you approve that exact proposal. The Python backend defaults to loopback and uses the standard library. The native client has pinned React/Tauri dependencies; remote serving requires explicit authenticated TLS configuration on a Tailscale IP.

## Status

Updated 2026-11-07: native Tauri + React + TypeScript Mac client, persistent streaming chat, owner authentication, guarded private TLS listener, project file previews, exact approvals/diffs, approved commands, diagnostics and verified SQLite snapshots are implemented. **Mission 1 is PARTIAL**: JARVIS SSH authentication was rejected, so no ZimaOS deployment or server-model evaluation has occurred.

The installed Mac `qwen2.5-coder:14b` completed a genuine synthetic coding workflow in 110.7 seconds, including patch, tests, evidence-checked completion and restart persistence. `llama3.2:3b` produced a valid patch and tests but repeated work instead of completing. No model was downloaded. These are local Mac observations, not server or general-quality certifications.

Verification: 177 Python tests discovered; HTTP-enabled run passed with 4 skips, default run passed with 34 skips; TypeScript/production build passed; 2 Vitest framing tests and 1 Rust connection-policy test passed. The actual Mac app was exercised, including token authentication and refusal of an untrusted TLS certificate.

Start the backend with `python3 app/server.py`; then follow [desktop setup](desktop/README.md). See the [criterion-by-criterion acceptance evidence](docs/MISSION_1_ACCEPTANCE.md), [threat review](docs/THREAT_MODEL.md), and [private deployment instructions](DEPLOYMENT.md). The Python backend remains authoritative for approvals. The native file pane is read-only and its terminal panel is an approved command runner; a general editor and PTY terminal remain planned.

## Architecture

```
Browser dashboard (web/)
        │  loopback JSON API
        ▼
Python control plane (app/server.py)  ──  SQLite (data/personal_codex.db)
        ├── approval policy + immutable decisions
        ├── Git worktree / release / merge lifecycle
        ├── command executor (no shell, allowlist, limits)
        ├── agent tool validator (app/tools.py)
        └── provider adapters (app/providers.py: Ollama, OpenAI-compatible)
```

- `app/server.py` — HTTP API, persistence, approval policy, worktree and command execution.
- `app/tools.py` — strict agent tool schema, workspace containment, patch application, round proposal parsing, feedback and completion evidence.
- `app/providers.py` — model HTTP adapters with timeout, size and endpoint hardening.
- `web/` — static dashboard; it has no filesystem or command capability of its own.
- `tests/` — standard-library `unittest` suites (no browser required).

## What works today

- Register an existing local repository and inspect a bounded, non-secret file inventory.
- Create a task and get a four-stage plan: planner → developer → testing → independent reviewer.
- Create an isolated Git worktree for a task, only after approval.
- Run one exact, allowlisted development command in that worktree, only after approval.
- Release a clean worktree, keeping its branch as a recovery checkpoint.
- Preview a merge read-only, merge after a critical approval bound to the reviewed commits, and delete the retained branch only after another approval.
- Register `ollama` and `openai-compatible` providers without ever storing a secret.
- Invoke an approved provider and keep a bounded, redacted response ledger.
- Ask a provider for an **agent proposal** of allowlisted tool calls, review it, approve it, and execute it inside the task worktree.
- Run an **iterative round loop**: execute an approved proposal, record the test evidence, and send that bounded evidence back to the provider for the next proposal. Every round needs its own approval, at most 3 rounds run by default (`PERSONAL_CODEX_MAX_ROUNDS`, 1–10), and a task cannot be declared complete without a passing executed round that changed files.
- **Cancel a running task** without losing completed work: the cancellation is persisted, checked before every tool, and passed into the command executor, which stops a running test command with SIGTERM and then SIGKILL after a 1.5 s grace period. Output written before the stop is preserved, the exit code is `130` so a cancelled run can never look like a passing one, completed operations are kept, skipped ones are recorded, and the cancelled round can never execute with its old approval.
- **Review a pending proposal as a diff:** each `apply_patch` is shown as a unified diff with the digest the proposal was bound to, the file's current digest, and an occurrence count. A file that changed after review is flagged stale and the round cannot be executed from that approval.
- **Watch activity live:** `GET /api/tasks/{id}/events/stream` streams persisted events as Server-Sent Events, using SQLite rowids as ids, so a reconnecting dashboard resumes from `Last-Event-ID` instead of replaying history. The stream is read-only, bounded and closed on a dead client.
- **Search a registered repository locally** (`GET /api/projects/{id}/search?q=`): case-insensitive, `.gitignore`-aware, and it never returns secret-named files, symlinks or generated directories. Results are capped in count and line length.
- Inspect every task's plan, events, executions, provider responses, proposal, round history, test results, final report and diff-facing operation list in the dashboard.
- See an **operation-level ledger** (status, timing, applied flag, file hashes) for each round and a **cumulative budget meter** (prompt, response, test output, context, invocations).
- Let the agent select **bounded repository context** locally: manifest, docs, test locations, symbol outlines, task/symbol/changed-file ranking, `.gitignore` and secret exclusion, symlink containment, byte caps, and a stable digest bound to the approved prompt.
- Record project-scoped **memory** entries (conventions, decisions, known issues, solved problems, test commands) that are inspectable, editable, deletable, bounded, credential-rejected and clearly marked as possibly stale in prompts.
- **Promote memory from evidence:** after a round passes, a memory record can be proposed, deduplicated, credential-checked, and stored only after explicit approval; the stored record keeps its source task, round, test command, exit code and changed files.
- **Stream provider output** (opt-in) with bounded, validated accumulation; an incomplete or malformed stream is rejected instead of becoming a proposal.
- **Diagnose a live provider** with `scripts/live_provider_check.py`: model discovery, a schema-validated probe, latency and byte counts, sanitised errors, and no repository writes.
- Inspect provider status (`ready` / `needs-attention`) and the last observed latency without contacting the provider.

Not implemented yet: provider-native tool calling, semantic/vector retrieval, deployed ZimaOS backend, OS-level execution/egress isolation, encrypted credential storage, general editor/PTY, signed/notarized distribution, automatic updates, scheduled backups, and broad UI regression automation. Native launch/auth/chat/workspace checks and a genuine Mac model workflow have been performed; remote operation remains blocked.

## Requirements

- macOS (Apple Silicon tested) or Linux.
- Python 3.11+ (3.13 recommended) with `sqlite3` and `git` on `PATH`.
- Node.js only for `node --check web/app.js`; the dashboard itself has no build step.
- Optional: [Ollama](https://ollama.com) or any OpenAI-compatible local server.

No packages need installing for the app or the tests. The optional Respan Gateway integration
(`respan-gateway==0.3.0`) is declared in `requirements.txt`; install it from wheels only with
`pip install --only-binary=:all: -r requirements.txt` inside a virtual environment.

## Run

```sh
git clone --branch personal-codex/stabilization https://github.com/SamarthRamesha/personal-codex.git
cd personal-codex
python3 app/server.py
# open http://127.0.0.1:8787
```

The database defaults to `data/personal_codex.db`; the entire data directory is Git-ignored. `PERSONAL_CODEX_DATA` selects a dedicated owned directory. Loopback development is unauthenticated unless `PERSONAL_CODEX_TOKEN_FILE` is configured. Non-loopback startup is refused unless the bind address is a Tailscale IP and owner-token authentication plus TLS certificate/key are configured. Wildcard, public and ordinary LAN binds are refused. See `DEPLOYMENT.md`; JARVIS has not been deployed.

## Configure a provider

### Ollama (local)

```sh
ollama serve
ollama pull qwen2.5-coder:7b
```

In the dashboard, register a provider with kind `ollama`, endpoint `http://127.0.0.1:11434`, and the model name you pulled. Requests go to `/api/chat` (or `/api/generate` if you give that path). No credential is needed.

### OpenAI-compatible local server (llama.cpp, LM Studio, vLLM)

Register kind `openai-compatible` with endpoint `http://127.0.0.1:<port>/v1`. Requests go to `/chat/completions`. If the server expects a key, add `secret_ref` naming an **environment variable**, never the value:

```sh
export LOCAL_MODEL_KEY="…"          # keep it out of git
python3 app/server.py
```

The key is read only when an approved invocation runs, is sent only in the `Authorization` header, and is never stored, returned, or logged.

### Local Respan Gateway (optional, disabled by default)

**2026-11-07 policy:** this gateway may route requests externally despite its local hop. It requires explicit `PERSONAL_CODEX_ENABLE_GATEWAY=1` plus a separate bound `network` approval for task invocations. It is absent from native local-provider selection. The historical integration instructions below do not constitute permission to enable it or supply credentials. No hosted integration was used in this milestone.

The pinned `respan-gateway==0.3.0` integration routes one provider call through the open-source
[Respan Gateway](https://github.com/respanai/respan-gateway?utm_source=freebuff&utm_medium=paid&utm_campaign=respan-gateway&bfcid=bfc_1.eyJpZCI6Ijc1NTA5Yjg1LTIwNDAtNGIwMC04MTFjLTkzNWFmZmUzNGVkYyIsImMiOiIyMDM2ODZkZS1mMzg0LTQ4NTQtYmViNC1hYzBiYWRmNmM1NTUiLCJrIjoiM2IxMGE4YmUtNzgyOS00MmJhLWFmNmEtYmI0YWUxZTRhY2Y4IiwiaWF0IjoxNzkzODgyMzMyfQ.XD_0nrLykffN6GdfZHgLtzA8DH3VooitSVkwVie7jQo), served in this process on a
loopback port it chooses itself (`gw.serve(port=0)`). The gateway holds the developer's own provider
keys — `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, or `env:NAME` references in a local
`gateway.toml` — and adds its routing, retry and fallback rules. Personal Codex keeps its single
hardened HTTP boundary: it sends the gateway no credential, applies the same byte caps, redirect
refusal and redaction, and still requires an approval for every call.

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install --only-binary=:all: -r requirements.txt
export OPENAI_API_KEY="…"        # the gateway's own key; keep it out of git
python3 app/server.py
```

Register a provider with kind `respan-gateway` and the model the gateway should route. Leave
`endpoint` and `secret_ref` empty: the provider record stores neither, and the loopback port is
chosen per process, so the approval binding stays stable. Round approvals, budgets, streaming and
response validation are unchanged. Nothing is exported: Respan signup, `RESPAN_API_KEY` and hosted
credits are not used. Keep the listener on loopback — without `client_keys` in its config, anyone
who reaches it spends your keys.

Check the route without a key or network:

```sh
python3 scripts/gateway_check.py          # add --json for a machine-readable report
```

It starts a loopback fixture provider, starts the gateway against it, then runs the app path —
register provider → request approval → approve → invoke — plus the streaming round path. Observed on
2026-11-05: every check reported `ok`, the fixture reply came back through the gateway (103 bytes, in
the plain and streamed path) and validated as an agent proposal. That proves routing, approval
binding and response validation; no live provider request was made in that run.

### Cloud endpoints

A non-loopback endpoint is accepted only when registered with `cloud_allowed: true` **and** a `secret_ref`. Each invocation additionally needs a separately approved `network` request: giving metadata consent is not transmission consent. Cloud adapters refuse to run without a secret reference.

## Agent workflow

1. Register a project and create a task describing the change.
2. Approve `workspace-request`, then create the workspace.
3. Click **Request round approval** (choose a provider). Personal Codex selects a bounded repository context (see below), builds a deterministic prompt from the task, that context, the round history and the tool schema, and queues an approval bound to that prompt's digest and round number. The selected files, their reasons, the byte count and the context digest are shown in the dashboard.
4. Approve it, then click **Propose next round**. The provider must answer with `{"summary", "status", "operations"}`; operations are validated against the closed tool schema and file hashes are bound; a second approval is queued for the round's proposal digest.
5. Approve that proposal and click **Execute approved round**. The tools run in the task worktree and the test exit code, output tail, changed files, and failed test names are recorded.
6. Repeat from step 3 — the next prompt contains the previous round's evidence, so a failure can be corrected. Rounds stop at the round, time, or budget limit, or when the provider returns `blocked`/`failed`. **Cancel round** or **Cancel task** records a cancellation: a pending proposal is closed immediately, an executing round stops before its next operation, completed operations are preserved, and the round's approval is revoked.
7. A `complete` status is accepted only if the evidence proves it: an executed round with a passing test command and at least one approved file change, and no later failing round. Model prose alone can never mark the task done.
8. Review execution results, the operation list, and the diff in the worktree; run tests through an approved command if needed.
9. Release the clean worktree, preview the merge, then merge and (optionally) delete the recovery branch, each with its own approval.

Allowed tools: `list_files`, `read_file`, `apply_patch` (exact single-match text replacement), `run_tests` (only allowlisted development commands). At most 8 operations per proposal, 3 rounds per task by default, and 30 minutes of wall-clock per task.

### Round lifecycle

`round/request` → approval → `round/plan` → proposal approval → `round/execute` → `passed` / `failed-checks` / `failed` → next `round/request`. Each round row persists its provider, model, prompt digest, proposal digest, approval, operations, results, test feedback, error, and timestamps, so a refreshed dashboard reconstructs the whole history. Duplicate provider responses and already-reviewed proposal digests are refused, and the run is limited by rounds, elapsed time, operations, and bounded feedback text. If the service restarts mid-execution, the next start marks the abandoned round `interrupted` (never `passed`), releases the task to `needs-another-round`, and requires a fresh proposal, so a crash can neither fake success nor wedge the loop.

### Cancellation and recovery

Cancellation is a recorded state, not a UI flag. `POST /api/tasks/{id}/cancel` (or the dashboard's **Cancel task**) stores a cancellation row bound to the active round, revokes that round's approved proposal, marks a not-yet-started round `cancelled`, and sets the task to `cancelled`. Execution consults that row before every operation, so a cancelled round stops starting new tools and test commands; operations that already ran keep their results and every skipped index is recorded as `cancelled`. Nothing is rolled back, and no cancelled operation is ever applied later. Requesting a new round after a cancellation is an explicit user action; it clears the cancellation record but still requires fresh provider and proposal approvals.

Each operation also has a ledger row: task, round, index, tool, approved proposal digest, status, start and finish time, result summary, error, whether an edit was applied, and the before/after SHA-256 of the file it touched. Rows are written before and after each tool runs, so a crash leaves a truthful record instead of a gap. On startup, rounds stuck in `executing` become `interrupted`, their proposals close, running operation rows become `interrupted` (they are never replayed), completed rows are preserved, and an `iterating` task moves to `needs-another-round`.

### Resource budgets

Cumulative usage is persisted per task (prompt bytes, provider response bytes, test output bytes, context bytes, invocations) and enforced before a provider call:

| Variable | Default | Meaning |
| --- | --- | --- |
| `PERSONAL_CODEX_MAX_ROUNDS` | `3` | rounds per task (1–10) |
| `PERSONAL_CODEX_MAX_TASK_SECONDS` | `1800` | wall-clock budget per task |
| `PERSONAL_CODEX_MAX_PROMPT_BYTES` | `800000` | total prompt bytes sent for the task |
| `PERSONAL_CODEX_MAX_RESPONSE_BYTES` | `300000` | total provider response bytes |
| `PERSONAL_CODEX_MAX_TEST_OUTPUT_BYTES` | `300000` | total retained test output |
| `PERSONAL_CODEX_MAX_CONTEXT_BYTES` | `60000` | repository context per round |
| `PERSONAL_CODEX_MAX_INVOCATIONS` | `12` | provider calls per task |

When a budget is exhausted the request is refused before any provider call, the task moves to `budget-exhausted`, the reason is written to the event log, and the dashboard shows the meter. Resuming requires an explicit `POST /api/tasks/{id}/agent/budget/reset` with `{"confirm": true}`; nothing resets automatically, and a reset still needs fresh approvals.

### Repository context and memory

`app/context.py` builds a bounded view of the repository without sending it anywhere: a manifest (file counts, extensions, config files, docs, tests, entry points), documentation and manifest prioritisation, a lightweight symbol outline (`ast` for Python, conservative regexes for JavaScript/TypeScript), and a ranked selection driven by task tokens, previously failed tests, changed files and symbol matches. It respects `.gitignore` and built-in ignored directories, refuses secret-named files, refuses symlinks that leave the workspace, caps each file and the whole selection, and returns a stable SHA-256 digest. The selected snippets are rendered into the approved prompt inside a block explicitly marked as untrusted repository data. `GET /api/tasks/{id}/agent/context` shows what was selected; the prompt text itself stays local and the context API never returns it.

Project memory is a foundation, not an authority: `GET/POST /api/projects/{id}/memory` and the `/memory/update` and `/memory/delete` routes store bounded entries (`convention`, `decision`, `issue`, `solved`, `relationship`, `test-command`, `summary`), reject credential-like content, and are injected into prompts under a "possibly stale; verify against the files" heading.

## Live Ollama test

Everything above is verified with a deterministic injected transport. A live model run has **not** been performed here; Ollama is not installed in the development environment and the owner's Mac is not reachable from it. The reproducible procedure is:

1. On the owner's Mac (Apple Silicon, 16 GB): `ollama serve`, then `ollama pull qwen2.5-coder:7b` (or any installed model — do not assume one is present; `ollama list` first).
2. Start Personal Codex: `python3 app/server.py`, open `http://127.0.0.1:8787`.
3. Register a disposable Git repository (a scratch copy with at least one test command) and a task such as "fix the failing greeting test".
4. Register provider kind `ollama`, endpoint `http://127.0.0.1:11434`, model from step 1.
5. Request round approval, approve it, propose the round, and review the JSON operations and the selected context.
6. Approve the proposal, execute the round, and check the test exit code, ledger, and context digest.
7. If it failed, request round 2 and confirm the next prompt contains the failure evidence. Repeat, then request completion and verify the final report.
8. Record what actually happened (JSON compliance, patch matching, test usefulness) in `DEVELOPMENT_LOG.md`; never report a live run that did not happen.

## Memory lifecycle

Memory is not free-form model text. A proposal can only be created after a round passed its checks (`POST /api/tasks/{id}/agent/memory/propose`), and it stores evidence: source task, round number, test command, exit code and changed files. The proposal is deduplicated against existing memory and pending proposals, rejected if it looks like a credential, and remains `pending` until the user approves or rejects it (`POST /api/memory-proposals/{id}/decide`). Approval copies it into project memory with its provenance; rejection stores nothing. A task that completes additionally queues one deterministic summary proposal derived from its verified report — also pending until approved. Memory reads report `stale: true` when the originating task is missing or no longer passed, and prompts label entries "verified against a passing round" or "possibly stale, verify against the files". Retrieval is relevance-ranked against the task and the selected context paths, capped by entries and bytes.

## Provider streaming and diagnostics

`OllamaStreamTransport` reads NDJSON chunks with `http.client` under a byte cap and a chunk cap, ignores proxies, refuses redirects and non-loopback hosts without cloud consent, honours a cancellation check between chunks, and fails on malformed chunks, error chunks, missing terminal `done`, oversized output or empty text. Only the completed, validated text can enter the approval lifecycle; partial output is never parsed as a proposal. Streaming defaults on (`PERSONAL_CODEX_STREAM_PROVIDER=1`); set `0` only for legacy non-streaming diagnostics and covers both Ollama NDJSON and OpenAI-compatible SSE (`data:` frames, terminated by `[DONE]`); an unterminated SSE stream is rejected, and a missing credential fails before any request.

`scripts/live_provider_check.py` is the only component intended to talk to a real model, and only when a human runs it. It lists installed models, requires an explicitly named model, sends one tiny probe, validates the JSON against the round schema, and reports latency, byte counts and sanitised errors. Exit codes: 0 pass, 2 no usable model, 3 invalid proposal, 4 provider failure. It never registers a project or modifies a repository.

```sh
python3 scripts/live_provider_check.py --discover-models
python3 scripts/live_provider_check.py --model <installed-model>
```

Provider HTTP error bodies are scrubbed of secret-shaped strings before they are shown or stored, and failures are classified (`unreachable`, `timeout`, `redirect`, `oversized`, `malformed`, `unauthorised`, `server-error`, `rejected`) so the diagnostic can explain them. Read-only model discovery may retry once on a connection failure; nothing that could modify a workspace is retried.

## Measured performance (this repository, Linux, Python 3.12)

| Operation | Result |
| --- | --- |
| `context.select` (24 files, 60 kB budget) | ~45 ms median, 12 files selected, 42.5 kB |
| `context.manifest` | ~3 ms |
| SQLite `events` query (50 rows) | ~0.11 ms |
| `GET /api/tasks`, `GET /` (loopback) | under 2 ms |

Provider latency is unknowable here because no model is installed; the diagnostic harness reports it on the owner's machine.

## Security model

- Loopback-only listener; no login or TLS, so never expose it. Every response carries `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Cache-Control: no-store`, and a restrictive Content-Security-Policy (`default-src 'self'` for the dashboard with no inline script or style, `default-src 'none'` for JSON APIs).
- Secret-named files (`.env`, keys, credentials files) are excluded from summaries, tool reads, and listings.
- Registration never reads a secret or contacts a provider.
- Approvals are immutable once decided, and are bound to exact state: prompt digest, provider/endpoint/model, workspace branch, proposal digest and file hashes.
- A changed file, changed proposal, changed Git state, or changed workspace invalidates the approval instead of reusing it.
- No shell: commands are parsed literally, restricted to a development allowlist, run only inside the task worktree, capped at 1–300 s with child resource limits, and redacted/bounded on output.
- Provider adapters ignore proxy environment variables, refuse redirects, and refuse non-loopback hosts unless the provider is cloud-consented.
- Model output never executes directly; only validated, approved tool calls run.
- Every round binds its own approval to the round number, prompt digest, workspace branch/path, proposal digest, and reviewed file hashes; a previous round's approval can never execute a new proposal.
- Completion claims are checked against recorded evidence, not model confidence, and a cancelled round invalidates its pending proposal.
- Execution output fed back to the provider is redacted and truncated, the workspace listing is capped, and repository context is budgeted and secret-free, so a round cannot stream unbounded or secret repository content to a cloud endpoint.
- Cancellation is persisted and checked before every operation; a cancelled round cannot reuse its approval, and completed operations are preserved rather than silently rolled back.
- Cumulative prompt, response, test-output, context and invocation budgets are enforced before a provider call; exhaustion stops the task instead of silently continuing, and only an explicit confirmed reset clears it.
- Merge and branch deletion are separate critical approvals; a dirty target worktree is refused.

Known limitations: no OS execution sandbox or guaranteed egress isolation, no guaranteed address-space enforcement on every OS, no encrypted secret store, no multi-user/project-scoped authorization, and no verified JARVIS deployment. CSP, owner authentication and configured TLS are implemented. Exact command approval does not make malicious repository test code safe.

## Tests

```sh
python3 -m unittest discover -s tests -v                              # 177 discovered, OK (skipped=34)
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # 177 discovered, OK (skipped=4)
python3 -m py_compile app/server.py app/providers.py app/tools.py app/context.py
node --check web/app.js
```

`tests/test_server.py` covers repository filtering, planning, approvals, worktree, command execution, release, merge and branch deletion. `tests/test_providers.py` runs both adapters against an ephemeral loopback stub server (malformed JSON, HTTP errors, redirects, refusal, timeout, oversize, credentials). `tests/test_tools.py` covers the tool schema, path/symlink containment, patch hash binding, execution ordering, the full proposal → approval → execution API lifecycle including stale-file rejection, and the iterative round loop: a failing round followed by a corrected passing round and an evidence-checked completion, per-round approvals, false-completion rejection, duplicate-response refusal, the round limit, and cancellation. `tests/test_ui.py` is a browser-free dashboard contract check (element IDs, wiring, routed API paths, local-only assets). `tests/test_context.py` covers the context engine (manifest, `.gitignore` and secret exclusion, symlink containment, ranking and determinism, byte and file caps, Python/JS outlines, untrusted-data framing) and the project-memory API (scoping, credential rejection, edit, delete). The round suite also covers cancellation between operations with partial-work preservation, operation-ledger persistence, interrupted operations not being replayed, invocation and prompt budget refusal, explicit budget reset, and context visibility/digest binding. `tests/test_gateway.py` covers the Respan Gateway provider (metadata rules, no stored endpoint or secret, network approval even for its loopback hop, the missing-package message, and a routed invocation plus streamed round against a loopback fixture). `tests/test_streaming.py` covers streaming accumulation and rejection (missing terminal marker, malformed chunk, oversized stream, cancellation, sanitised HTTP errors), model discovery, error redaction, and the live diagnostic harness (unreachable service, no models, missing explicit model, valid probe, invalid JSON). The memory suite covers evidence requirements, duplicate refusal, credential refusal, explicit approval/rejection, provenance, staleness labelling and retrieval bounds. No live model and no external network are used.

## Project documents

`PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEPLOYMENT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, and `NEXT_SESSION_PROMPT.md` (permanent cross-account handoff).

## Roadmap

1. A verified live Ollama round on the owner's machine (the immediate priority).
2. Provider-native tool calls.
3. A lightweight semantic retrieval benchmark before any embedding dependency is considered.
4. Extend native parity: editor, PTY, memory and Git review controls; native shell is implemented.
5. Mutually authenticated ZimaOS worker on a private network.
