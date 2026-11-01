# Architecture

## v0 implemented boundary

`Browser UI → loopback Python control plane → SQLite`

The control plane is the policy and persistence boundary. It accepts repository paths only after local validation, produces bounded repository inventories, and stores durable task state. The UI contains no privileged filesystem or command capability.

Execution is two-phase: a user requests a task worktree or an exact command; an approved matching record is required before the API creates the worktree or runs the command. Commands are parsed without a shell, limited to a development-tool allowlist, run only inside the task worktree with a bounded environment and timeout, and have common secret assignment patterns redacted from retained output.

After a clean workspace release, its task branch is a recovery checkpoint. The user may obtain a read-only merge preview; conflicts are reported without touching the target repository. A conflict-free merge requires a distinct critical approval that canonically records both branch names and their reviewed commit IDs. The service refuses to merge if either commit changes. After a merge, deleting the retained recovery branch is separately critical-approved and bound to its reviewed commit ID.

## Intended progression

1. Keep this control-plane API stable.
2. Add a native Tauri + React shell that talks to the loopback service.
3. Introduce explicit capability tokens and a command/worktree runner operating only in assigned workspaces.
4. Add provider adapters behind a routing interface; local-only remains a first-class policy.
5. Add a mutually authenticated ZimaOS worker protocol over a private network; never expose an unauthenticated worker.

## Data model

- `projects`: approved local roots.
- `tasks`: request, plan, state, timestamps.
- `events`: immutable agent activity entries.
- `approvals`: permission gates for execution, network, or critical actions.
- `providers`: endpoint/model metadata plus an environment secret reference, never the secret value.
- `workspaces`: task-owned path, recovery branch, and lifecycle state (`ready`, `released`, `merged`, or `complete`).

SQLite is appropriate for a single-user Mac control plane. A remote worker should own its own durable queue rather than share the SQLite file across a network filesystem.
