# Personal Codex

Personal Codex is a private, local-first AI coding control plane for macOS. It connects a registered Git repository, a local or explicitly consented model provider, and a task workspace where an agent can propose — and you can approve — small, auditable code changes.

Nothing is autonomous by default. A model may *propose* file edits and test commands as strict JSON; Personal Codex validates them, shows you the exact digest, and only applies them to an isolated Git worktree after you approve that exact proposal. The service listens on loopback only and has no third-party runtime dependencies.

## Status

Working vertical slice, standard library only (Python 3.11+ / tested on 3.12 and 3.13). There is no installer, no desktop shell, and no remote worker yet. Everything runs from `python3 app/server.py`.

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
- `app/tools.py` — strict agent tool schema, workspace containment, patch application.
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
- Inspect every task's plan, events, executions, provider responses, proposal and diff-facing operation list in the dashboard.

Not implemented yet: provider streaming, provider-native tool calling, multi-round agent loops, desktop shell, ZimaOS worker, indexer/LSP, login/TLS, encrypted secret storage, conflict-resolution tooling, and browser automation tests.

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
3. Click **Request agent plan approval** (choose a provider). Personal Codex builds a deterministic prompt from the task, the visible workspace files, and the tool schema, and queues an approval bound to that prompt's digest.
4. Approve it, then click **Build approved plan**. The provider's JSON is validated against a closed tool schema; file hashes are bound; a second approval is queued for the proposal digest.
5. Approve that proposal and click **Execute approved plan**.
6. Review execution results, the operation list, and the diff in the worktree; run tests through an approved command if needed.
7. Release the clean worktree, preview the merge, then merge and (optionally) delete the recovery branch, each with its own approval.

Allowed tools: `list_files`, `read_file`, `apply_patch` (exact single-match text replacement), `run_tests` (only allowlisted development commands). At most 8 operations per proposal.

## Security model

- Loopback-only listener; no login or TLS, so never expose it.
- Secret-named files (`.env`, keys, credentials files) are excluded from summaries, tool reads, and listings.
- Registration never reads a secret or contacts a provider.
- Approvals are immutable once decided, and are bound to exact state: prompt digest, provider/endpoint/model, workspace branch, proposal digest and file hashes.
- A changed file, changed proposal, changed Git state, or changed workspace invalidates the approval instead of reusing it.
- No shell: commands are parsed literally, restricted to a development allowlist, run only inside the task worktree, capped at 1–300 s with child resource limits, and redacted/bounded on output.
- Provider adapters ignore proxy environment variables, refuse redirects, and refuse non-loopback hosts unless the provider is cloud-consented.
- Model output never executes directly; only validated, approved tool calls run.
- Merge and branch deletion are separate critical approvals; a dirty target worktree is refused.

Known limitations: no OS sandboxing, no guaranteed address-space enforcement on every OS, no encrypted secret store, no CSP headers, no authentication, and no TLS.

## Tests

```sh
python3 -m unittest discover -s tests -v                              # 56 tests; listener-gated ones skipped
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v  # all 56 tests, disposable fixtures
python3 -m py_compile app/server.py app/providers.py app/tools.py
node --check web/app.js
```

`tests/test_server.py` covers repository filtering, planning, approvals, worktree, command execution, release, merge and branch deletion. `tests/test_providers.py` runs both adapters against an ephemeral loopback stub server (malformed JSON, HTTP errors, redirects, refusal, timeout, oversize, credentials). `tests/test_tools.py` covers the tool schema, path/symlink containment, patch hash binding, execution ordering, and the full proposal → approval → execution API lifecycle, including stale-file rejection. `tests/test_ui.py` is a browser-free dashboard contract check (element IDs, wiring, routed API paths, local-only assets). No live model and no external network are used.

## Project documents

`PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `HANDOFF.md`, `DEPLOYMENT.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, and `NEXT_SESSION_PROMPT.md` (permanent cross-account handoff).

## Roadmap

1. Multi-round agent loop: feed bounded test results back to the provider, capped by round and time limits.
2. Streaming and provider-native tool calls.
3. Project memory from manifests, docs, and parsed symbols.
4. Tauri desktop shell over the loopback API.
5. Mutually authenticated ZimaOS worker on a private network.
