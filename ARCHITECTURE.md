# Architecture

## v0 implemented boundary

`Browser UI → loopback Python control plane → SQLite`

The control plane is the policy and persistence boundary. It accepts repository paths only after local validation, produces bounded repository inventories, and stores durable task state. The UI contains no privileged filesystem or command capability.

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

SQLite is appropriate for a single-user Mac control plane. A remote worker should own its own durable queue rather than share the SQLite file across a network filesystem.
