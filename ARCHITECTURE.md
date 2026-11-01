# Architecture

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

## Provider invocation boundary

Invocation is a three-record flow: `provider-request` creates a pending approval whose canonical detail binds task, provider ID, endpoint, model, prompt SHA-256, and cloud flag; the user decides once; `invoke` requires the matching approved record before calling the adapter. Loopback providers use the `provider-invoke` approval kind; a provider registered with `cloud_allowed: true` requires a distinct `network` approval, so metadata consent and transmission consent stay separate.

The adapter itself only receives a request object of kind, endpoint, model, prompt, and cloud flag. It never receives the environment-variable reference or any secret value. `active_provider_transport` resolves the adapter per invocation: `app/providers.py` supplies the built-in Ollama and OpenAI-compatible adapters, while setting `server.PROVIDER_TRANSPORT` injects a deterministic transport for tests or offline use.

`app/providers.py` is standard-library only: `http.client` requests (no `urllib` opener, so proxy environment variables are ignored and redirects are never followed), a fixed connection timeout, a 1 MB response cap, JSON shape validation, and sanitised error text. Loopback-only enforcement is repeated inside the adapter, so a local provider cannot be redirected to an external host. OpenAI-compatible credentials are resolved from the named environment variable at call time inside a closure and placed only in the request header.

Only bounded, redacted response text and the prompt digest are persisted in `invocations`; the prompt is not stored there.

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
