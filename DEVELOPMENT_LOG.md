# Development log

## 2026-11-01

Environment discovered: Apple Silicon macOS (Darwin 25.6.0), Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite CLI, SSH client; Docker and Rust/Cargo were not found on PATH. Workspace volume had approximately 76 GiB free. The visible Mac address was 192.168.1.11. ZimaOS was not inspected because no server endpoint or authorization was available.

Created an isolated Git repository in this deliverable. Used no third-party runtime dependencies. Unit tests passed (4/4). A listener smoke test failed at bind time with sandbox `PermissionError`; it was not retried because policy changed neither the port nor the permission model.

Added and unit-tested a capability-gated executor. Worktree creation needs a matching approved `modify` record. Command execution needs a matching approved `execute` record, uses no shell, is restricted to a task-owned workspace, supports a 1–300 second timeout, records redacted output, and emits an audit event. UI wiring and end-to-end HTTP tests remain outstanding. An approved unsandboxed loopback smoke test later confirmed the health endpoint and dashboard respond; process was stopped immediately.

Completed UI wiring for the approval and execution workflow. Approval decisions are now immutable after a first approved/rejected decision. Node syntax validation should be run after this UI change; no automated browser or HTTP integration harness has been added yet.

Ran the updated unit, Python compilation, JavaScript syntax, and loopback asset smoke checks successfully. The loopback server was stopped after verification.

Added an opt-in in-process HTTP integration test. It creates an initialised temporary Git fixture and switches the app to temporary SQLite/workspace storage, asserts both denied pre-approval operations and allowed post-approval operations, then shuts down the server and removes temporary data. With `PERSONAL_CODEX_HTTP_TESTS=1`, all seven tests passed in 0.646 seconds.

Added execution resource caps and critical-approval clean-worktree release. The initial strict resource setup failed in this macOS environment during child-process startup; corrected it by capping each resource independently and ignoring only OS-rejected limit types. The full lifecycle suite then passed 8/8 in 0.674 seconds, including release/recovery verification. No branch merge or deletion was implemented.
