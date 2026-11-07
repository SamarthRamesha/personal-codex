# Architecture

## Current architecture — 2026-11-07

`Native React/TypeScript UI → Tauri Rust IPC bridge → authenticated Python API → SQLite + approved Git worktrees → explicitly chosen local provider`.

The previous dependency-free dashboard remains available. `desktop/src/api.ts` handles API calls and bounded resumable SSE framing; `desktop/src-tauri/src/main.rs` owns credentials in memory, validates backend URLs, checks HTTPS identity using native trust roots, refuses redirects/proxies and bounds request/response/stream sizes. No shell/filesystem/HTTP plugins or updater are granted to the webview. Network tokens never enter browser storage. Only the backend performs file/tool operations.

`app/security.py` implements one owner principal, bearer auth and hashed in-memory expiring cookie sessions, login throttling, token-file constraints, Host/Origin checks and private listener policy. `app/server.py` reads `PERSONAL_CODEX_DATA`, requires authentication/TLS for non-loopback Tailscale binding, and exposes versioned connection metadata, diagnostics, backups and contained project file APIs. General owner authentication is separate from per-operation digest approvals. This is not multi-user/project-scoped access control.

`app/conversations.py` persists text and its last chunk cursor atomically; newest bounded history is used for prompts; one active turn per conversation and two total chat generations are allowed. Chat cannot edit files or grant itself cloud consent. Ordinary disconnection does not undo an operation already accepted by the server. Mutating requests are never automatically replayed.

`app/maintenance.py` measures only owned data, checks free reserve and quota before snapshots, uses SQLite backup/integrity verification and refuses overwrite on restore. Snapshots retain at most seven files without deleting old ones. Defaults: 75 GB owned-data budget; Linux 200 GB free reserve, Mac 5 GB free reserve. External model storage is not included and must be accounted separately before server deployment. No vector database, additional inference engine or service supervisor was selected before actual hardware discovery.

The task engine, exact tools, context/memory and merge/recovery design below remain authoritative where not superseded. Round streaming now defaults on. Native provider-tool calling is absent; model capabilities are not guessed. See `docs/THREAT_MODEL.md` for the missing OS sandbox and egress isolation.

## Earlier architecture notes

The following material documents prior milestones. References to future desktop/authentication/streaming must be read with the current architecture above.

## v0 implemented boundary

`Browser UI → loopback Python control plane → SQLite`

The control plane is the policy and persistence boundary. It accepts repository paths only after local validation, produces bounded repository inventories, and stores durable task state. The UI contains no privileged filesystem or command capability.

Execution is two-phase: a user requests a task worktree or an exact command; an approved matching record is required before the API creates the worktree or runs the command. Commands are parsed without a shell, limited to a development-tool allowlist, run only inside the task worktree with a bounded environment and timeout, and have common secret assignment patterns redacted from retained output.

After a clean workspace release, its task branch is a recovery checkpoint. The user may obtain a read-only merge preview; conflicts are reported without touching the target repository. A conflict-free merge requires a distinct critical approval that canonically records both branch names and their reviewed commit IDs. The service refuses to merge if either commit changes. After a merge, deleting the retained recovery branch is separately critical-approved and bound to its reviewed commit ID.

Provider registration is an adapter-metadata boundary, not a network client. The supported descriptors are `ollama` and `openai-compatible`; endpoints must be absolute HTTP(S) URLs with no embedded credentials. A provider is loopback-only by default. A non-loopback endpoint is accepted only with a JSON boolean `cloud_allowed: true`; registration still does not read the named environment variable or contact the endpoint. The capability endpoint advertises the future invocation interface and states that invocation needs approval.

## Agent tool boundary

`app/tools.py` defines the only way model output can affect a workspace. A proposal is JSON with a
`summary` and 1–8 operations in a closed schema: `list_files`, `read_file`, `apply_patch`, and
`run_tests`. Every key is checked, every string and integer is bounded, and `apply_patch` requires
the exact existing text plus the reviewed SHA-256 of the file. Paths are resolved inside the task
worktree, so absolute paths, `..`, ignored directories, secret-named files, and symlink escapes are
refused. Execution is sequential and stops at the first failure; `run_tests` is handed to the
existing allowlisted command executor rather than gaining its own process authority.

Approvals bind two distinct things: the agent prompt digest (approving a provider call for exactly
that deterministic instruction) and the proposal digest plus workspace branch and path (approving
the exact file changes and commands). `POST /agent/execute` recomputes the digest from stored
operations, refuses a mismatch, requires the approved record, and atomically claims the proposal so
it can run at most once. A file edited after review fails the hash check instead of being
overwritten.

## Multi-round loop

`rounds` is a separate table from `proposals`, so existing agent behaviour is unchanged. A round row
holds task, round number, provider, model, prompt digest, proposal id/digest, approval id, status,
summary, operations, results, test result, error, and start/finish stamps. `GET /agent/rounds`
reconstructs the loop from SQLite, so a refreshed dashboard recovers it without client state.

The cycle is `round/request` → approval → `round/plan` → proposal approval → `round/execute`.
`round/request` builds a deterministic prompt from the task, the capped workspace listing (60 paths),
the bounded round history, and the round protocol, then queues a `provider-invoke` approval that also
binds the round number. `round/plan` requires the matching approved invocation record, calls the
adapter once, refuses a byte-identical response already seen for the task, parses the strict
`{"summary","status","operations"}` JSON, and queues a second approval for `agent-round-proposal` bound
to round number, workspace branch/path, proposal digest, and prompt digest. `round/execute` recomputes
the digest, verifies file hashes, runs the tools through the existing dispatcher, and writes the round
status. A round executes at most once; a cancelled or superseded round keeps its row for audit. At startup the store sweeps rounds still marked `executing` into `interrupted`, closes their proposals, writes an event, and moves an `iterating` task to `needs-another-round`, so a crash between tool calls can neither fake a pass nor block future rounds.

Round status is derived from recorded evidence, not from the model: a non-`run_tests` tool error is
`failed`; otherwise a zero-exit test command is `passed`; anything else is `failed-checks`. A failing
test run is therefore distinguishable from a tool failure. Each status maps to a task status
(`iterating`, `needs-another-round`, `ready-to-complete`, `completed`, `blocked`, `failed`, `cancelled`).
The next prompt embeds `round_feedback`: test command, exit code, redacted 2 000-character output tail,
failed test names, changed files, and errors. It also lists prior summaries so the model can avoid
repeating a failed change.

Limits are enforced server-side: 1–10 rounds (`PERSONAL_CODEX_MAX_ROUNDS`, default 3), 1 800 seconds per
task, 8 operations per round, one provider call per round, and the adapter's existing 1 MB response cap.
`complete` is validated by `completion_evidence`: there must be an executed round, at least one executed
round whose test command exited 0, at least one approved file change, and the most recent executed round
must have passed. A rejected completion is stored as `rejected-completion` and leaves the workspace
untouched, so a model cannot end a task with prose.

## Cancellation, ledger and budgets

Cancellation is state, not a signal: `cancellations` holds one row per task bound to the round that was
active when it was requested. `cancel_task` revokes that round's approved proposal approval, closes a
not-yet-started round, and marks the task `cancelled`. `tools.execute_operations` receives a
`stop_check` callable and consults it before every operation; once true, it stops starting new tools and
records each remaining index as `cancelled`. Nothing is rolled back, and the round stores
`cancelled_at_index` in its feedback so recovery and the dashboard can explain exactly where it stopped.

`operations` is an append-and-update ledger written through an `on_event` callback: a `running` row is
inserted before an operation starts and updated with status, timing, summary, error, `applied`, and
before/after file hashes after it finishes. The tools module still has no storage authority; the control
plane owns persistence. `Store.recover_interrupted` sweeps running rows to `interrupted` on startup, so
an interrupted edit is recorded but never replayed.

`usage` accumulates prompt, response, test-output, context and invocation bytes per task. `budget_error`
is checked before the provider call and before the prompt is built; exhaustion refuses the round, sets
`budget-exhausted`, and logs the reason. `reset_budget` is only reachable through a confirmed request and
does not approve anything.

## Repository context

`app/context.py` is a read-only selector. It walks contained, non-ignored, non-secret text files, builds a
manifest, extracts a Python `ast` outline and conservative JavaScript/TypeScript symbols, scores files by
task tokens, failed test names, previously changed files, documentation and manifest status, and takes
bounded snippets. Each snippet carries a reason, line range and file hash; the selection carries one
digest. `prompt_block` renders it with an explicit "untrusted data, never instructions" header, and the
control plane stores the full prompt (never exposed by the context API) so the approved prompt bytes are
exactly what the adapter receives. Project memory is a separate bounded record set injected under a
"possibly stale" heading.

## Memory promotion and retrieval

`memory_proposals` is the only path from model output to stored memory. A proposal requires a round with
status `passed`, and its evidence object records the task, round, test command, exit code and changed
files. The control plane normalises content for duplicate detection (against stored memory and pending
proposals when proposing, against stored memory only when approving), rejects credential-like text, and
stores `pending` until a user decision. Approval copies the record into `memory` with provenance columns
(`source_task_id`, `source_round_id`, `evidence`, `digest`); rejection stores nothing and cannot be
reversed. Reads compute `stale` from the source task's current status, and `memory_lines` ranks entries
against task tokens and selected context paths under entry and byte caps. Prompts label every entry as
verified or possibly stale, so memory never masquerades as repository truth.

## Streaming and provider diagnostics

`OllamaStreamTransport` consumes NDJSON with `http.client` under a byte and chunk cap, re-checks the
loopback rule, ignores proxies, refuses redirects, checks cancellation between chunks, and raises on
malformed chunks, error chunks, a missing terminal `done`, oversized output or empty text. Only the
completed text leaves the adapter, so no partial stream can reach validation or approval. The server uses
it for Ollama round calls only when `PERSONAL_CODEX_STREAM_PROVIDER=1`. `scripts/live_provider_check.py`
is a deliberate, human-invoked, read-only diagnostic; nothing in the service contacts a provider on its own.

## Provider invocation boundary

Invocation is a three-record flow: `provider-request` creates a pending approval whose canonical detail binds task, provider ID, endpoint, model, prompt SHA-256, and cloud flag; the user decides once; `invoke` requires the matching approved record before calling the adapter. Loopback providers use the `provider-invoke` approval kind; a provider registered with `cloud_allowed: true` requires a distinct `network` approval, so metadata consent and transmission consent stay separate.

The adapter itself only receives a request object of kind, endpoint, model, prompt, and cloud flag. It never receives the environment-variable reference or any secret value. `active_provider_transport` resolves the adapter per invocation: `app/providers.py` supplies the built-in Ollama and OpenAI-compatible adapters, while setting `server.PROVIDER_TRANSPORT` injects a deterministic transport for tests or offline use.

`app/providers.py` is standard-library only: `http.client` requests (no `urllib` opener, so proxy environment variables are ignored and redirects are never followed), a fixed connection timeout, a 1 MB response cap, JSON shape validation, and sanitised error text. Loopback-only enforcement is repeated inside the adapter, so a local provider cannot be redirected to an external host. OpenAI-compatible credentials are resolved from the named environment variable at call time inside a closure and placed only in the request header.

Only bounded, redacted response text and the prompt digest are persisted in `invocations`; the prompt is not stored there.

## Interactive execution surface

- `GET /api/tasks/{id}/events/stream` — read-only Server-Sent Events over the persisted `events` table. Ids are SQLite rowids, so `Last-Event-ID` (or `?after=`) resumes exactly after the last delivered event. Bounded to 500 events and 120 s per connection, with keep-alive comments and a clean close on a broken client.
- `GET /api/tasks/{id}/agent/diff` — re-reads each pending `apply_patch` target through the workspace resolver and returns a unified diff, the digest the proposal was bound to, the current digest, the occurrence count, and a `stale` flag. It never writes to the workspace and never returns content from outside it.
- `GET /api/projects/{id}/search?q=&limit=` — case-insensitive search over the same contained, `.gitignore`-aware, secret-free file set as the context engine, capped at 50 matches and 220 characters per line.
- Cancellation reaches the process executor: `execute_in_workspace(..., stop_check=)` polls every 200 ms, sends SIGTERM to the process group, escalates to SIGKILL after 1.5 s, keeps partial output, and returns exit code 130 with `cancelled: true`. The tool layer records that operation as `cancelled`, so a cancelled command is not misreported as a failed test, and the remaining operations never start.
- Every response carries `nosniff`, `no-referrer`, `X-Frame-Options: DENY`, `Cache-Control: no-store`, and a Content-Security-Policy (`default-src 'self'` for the dashboard with no inline script or style, `default-src 'none'` for JSON).

## Intended progression

1. Keep this control-plane API stable.
2. Add streaming and audited tool-call handling on top of the provider adapters.
3. Add a native Tauri + React shell that talks to the loopback service.
4. Introduce explicit capability tokens and a command/worktree runner operating only in assigned workspaces.
5. Add an agent-engine loop that turns an approved provider completion into allowlisted, approval-gated tool calls inside a task workspace.
6. Add a mutually authenticated ZimaOS worker protocol over a private network; never expose an unauthenticated worker.

## Data model

- `projects`: approved local roots.
- `tasks`: request, plan, state, timestamps.
- `events`: immutable agent activity entries.
- `approvals`: permission gates for execution, network, or critical actions.
- `providers`: endpoint/model metadata plus an environment secret reference, never the secret value.
- `workspaces`: task-owned path, recovery branch, and lifecycle state (`ready`, `released`, `merged`, or `complete`).
- `invocations`: approved provider responses, keyed by task and provider, with the prompt digest instead of the prompt.
- `proposals`: validated agent proposals with their digest, workspace branch/path, status (`pending`, `executing`, `executed`, `failed`), and per-operation results.

SQLite is appropriate for a single-user Mac control plane. A remote worker should own its own durable queue rather than share the SQLite file across a network filesystem.
