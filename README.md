# Personal Codex

Personal Codex is a private, local-first AI coding control plane for macOS. It connects a registered Git repository, a local or explicitly consented model provider, and a task workspace where an agent can propose — and you can approve — small, auditable code changes.

Nothing is autonomous by default. A model may *propose* file edits and test commands as strict JSON; Personal Codex validates them, shows you the exact digest, and only applies them to an isolated Git worktree after you approve that exact proposal. The service listens on loopback only and has no third-party runtime dependencies.

## Status

Working iterative coding loop, standard library only (Python 3.11+ / tested on 3.12 and 3.13). There is no installer, no desktop shell, and no remote worker yet. Everything runs from `python3 app/server.py`.

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
- Inspect every task's plan, events, executions, provider responses, proposal, round history, test results, final report and diff-facing operation list in the dashboard.

Not implemented yet: provider streaming, provider-native tool calling, project memory/indexer, desktop shell, ZimaOS worker, login/TLS, encrypted secret storage, conflict-resolution tooling, and browser automation tests.

## Requirements

- macOS (Apple Silicon tested) or Linux.
- Python 3.11+ (3.13 recommended) with `sqlite3` and `git` on `PATH`.
- Node.js only for `node --check web/app.js`; the dashboard itself has no build step.
- Optional: [Ollama](https://ollama.com) or any OpenAI-compatible local server.

No packages need installing: `pip install` is not required for the app or the tests.

## Run

```sh
git clone https://github.com/SamarthRamesha/personal-codex.git
cd personal-codex
python3 app/server.py
# open http://127.0.0.1:8787
```

The database is created at `data/personal_codex.db` (gitignored). Override the listener with `PERSONAL_CODEX_HOST` and `PERSONAL_CODEX_PORT`; keep it on loopback. Do not expose this service to a LAN or the internet — it has no authentication or TLS.

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

### Cloud endpoints

A non-loopback endpoint is accepted only when registered with `cloud_allowed: true` **and** a `secret_ref`. Each invocation additionally needs a separately approved `network` request: giving metadata consent is not transmission consent. Cloud adapters refuse to run without a secret reference.

## Agent workflow

1. Register a project and create a task describing the change.
2. Approve `workspace-request`, then create the workspace.
3. Click **Request round approval** (choose a provider). Personal Codex builds a deterministic prompt from the task, the visible workspace files, the round history, and the tool schema, and queues an approval bound to that prompt's digest and round number.
4. Approve it, then click **Propose next round**. The provider must answer with `{"summary", "status", "operations"}`; operations are validated against the closed tool schema and file hashes are bound; a second approval is queued for the round's proposal digest.
5. Approve that proposal and click **Execute approved round**. The tools run in the task worktree and the test exit code, output tail, changed files, and failed test names are recorded.
6. Repeat from step 3 — the next prompt contains the previous round's evidence, so a failure can be corrected. Rounds stop at the limit or when the provider returns `blocked`/`failed`; `cancel round` stops the loop and makes its pending approval unusable.
7. A `complete` status is accepted only if the evidence proves it: an executed round with a passing test command and at least one approved file change, and no later failing round. Model prose alone can never mark the task done.
8. Review execution results, the operation list, and the diff in the worktree; run tests through an approved command if needed.
9. Release the clean worktree, preview the merge, then merge and (optionally) delete the recovery branch, each with its own approval.

Allowed tools: `list_files`, `read_file`, `apply_patch` (exact single-match text replacement), `run_tests` (only allowlisted development commands). At most 8 operations per proposal, 3 rounds per task by default, and 30 minutes of wall-clock per task.

### Round lifecycle

`round/request` → approval → `round/plan` → proposal approval → `round/execute` → `passed` / `failed-checks` / `failed` → next `round/request`. Each round row persists its provider, model, prompt digest, proposal digest, approval, operations, results, test feedback, error, and timestamps, so a refreshed dashboard reconstructs the whole history. Duplicate provider responses and already-reviewed proposal digests are refused, and the run is limited by rounds, elapsed time, operations, and bounded feedback text. If the service restarts mid-execution, the next start marks the abandoned round `interrupted` (never `passed`), releases the task to `needs-another-round`, and requires a fresh proposal, so a crash can neither fake success nor wedge the loop.

## Security model

- Loopback-only listener; no login or TLS, so never expose it.
- Secret-named files (`.env`, keys, credentials files) are excluded from summaries, tool reads, and listings.
- Registration never reads a secret or contacts a provider.
- Approvals are immutable once decided, and are bound to exact state: prompt digest, provider/endpoint/model, workspace branch, proposal digest and file hashes.
- A changed file, changed proposal, changed Git state, or changed workspace invalidates the approval instead of reusing it.
- No shell: commands are parsed literally, restricted to a development allowlist, run only inside the task worktree, capped at 1–300 s with child resource limits, and redacted/bounded on output.
- Provider adapters ignore proxy environment variables, refuse redirects, and refuse non-loopback hosts unless the provider is cloud-consented.
- Model output never executes directly; only validated, approved tool calls run.
- Every round binds its own approval to the round number, prompt digest, workspace branch/path, proposal digest, and reviewed file hashes; a previous round's approval can never execute a new proposal.
- Completion claims are checked against recorded evidence, not model confidence, and a cancelled round invalidates its pending proposal.
- Execution output fed back to the provider is redacted and truncated, and the workspace listing is capped, so a round cannot stream unbounded repository content to a cloud endpoint.
- Merge and branch deletion are separate critical approvals; a dirty target worktree is refused.

Known limitations: no OS sandboxing, no guaranteed address-space enforcement on every OS, no encrypted secret store, no CSP headers, no authentication, and no TLS.

## Tests

```sh
python3 -m unittest discover -s tests -v                              # 66 tests; listener-gated ones skipped
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # all 66 tests, disposable fixtures
python3 -m py_compile app/server.py app/providers.py app/tools.py
node --check web/app.js
```

`tests/test_server.py` covers repository filtering, planning, approvals, worktree, command execution, release, merge and branch deletion. `tests/test_providers.py` runs both adapters against an ephemeral loopback stub server (malformed JSON, HTTP errors, redirects, refusal, timeout, oversize, credentials). `tests/test_tools.py` covers the tool schema, path/symlink containment, patch hash binding, execution ordering, the full proposal → approval → execution API lifecycle including stale-file rejection, and the iterative round loop: a failing round followed by a corrected passing round and an evidence-checked completion, per-round approvals, false-completion rejection, duplicate-response refusal, the round limit, and cancellation. `tests/test_ui.py` is a browser-free dashboard contract check (element IDs, wiring, routed API paths, local-only assets). No live model and no external network are used.

## Project documents

`PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEPLOYMENT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, and `NEXT_SESSION_PROMPT.md` (permanent cross-account handoff).

## Roadmap

1. Streaming and provider-native tool calls.
2. Project memory from manifests, docs, and parsed symbols.
3. Tauri desktop shell over the loopback API.
4. Mutually authenticated ZimaOS worker on a private network.
