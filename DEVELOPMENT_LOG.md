# Development log

## 2026-11-01

Environment discovered: Apple Silicon macOS (Darwin 25.6.0), Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite CLI, SSH client; Docker and Rust/Cargo were not found on PATH. Workspace volume had approximately 76 GiB free. The visible Mac address was 192.168.1.11. ZimaOS was not inspected because no server endpoint or authorization was available.

Created an isolated Git repository in this deliverable. Used no third-party runtime dependencies. Unit tests passed (4/4). A listener smoke test failed at bind time with sandbox `PermissionError`; it was not retried because policy changed neither the port nor the permission model.

Added and unit-tested a capability-gated executor. Worktree creation needs a matching approved `modify` record. Command execution needs a matching approved `execute` record, uses no shell, is restricted to a task-owned workspace, supports a 1–300 second timeout, records redacted output, and emits an audit event. UI wiring and end-to-end HTTP tests remain outstanding. An approved unsandboxed loopback smoke test later confirmed the health endpoint and dashboard respond; process was stopped immediately.

Completed UI wiring for the approval and execution workflow. Approval decisions are now immutable after a first approved/rejected decision. Node syntax validation should be run after this UI change; no automated browser or HTTP integration harness has been added yet.

Ran the updated unit, Python compilation, JavaScript syntax, and loopback asset smoke checks successfully. The loopback server was stopped after verification.

Added an opt-in in-process HTTP integration test. It creates an initialised temporary Git fixture and switches the app to temporary SQLite/workspace storage, asserts both denied pre-approval operations and allowed post-approval operations, then shuts down the server and removes temporary data. With `PERSONAL_CODEX_HTTP_TESTS=1`, all seven tests passed in 0.646 seconds.

Added execution resource caps and critical-approval clean-worktree release. The initial strict resource setup failed in this macOS environment during child-process startup; corrected it by capping each resource independently and ignoring only OS-rejected limit types. The full lifecycle suite then passed 8/8 in 0.674 seconds, including release/recovery verification. No branch merge or deletion was implemented.

Completed recovery-branch controls. A clean released task branch can be previewed with `git merge-tree --write-tree`; conflicts are returned without modifying the target. A merge requires a separate critical approval bound to the source and target commit IDs, preventing approval reuse if reviewed Git state changes. A merged branch can be deleted only after another critical approval bound to its commit ID and an ancestry check. Added a conflict-preview unit test and extended the opt-in HTTP lifecycle test through merge and branch deletion.

Verified the completed merge lifecycle: default tests passed 8 unit tests with the listener test intentionally skipped; with `PERSONAL_CODEX_HTTP_TESTS=1`, all 9 tests passed. The HTTP lifecycle also asserts that a target-branch commit after approval makes the old merge approval unusable, requiring a new review and approval.

Added provider-adapter metadata validation. The control plane now accepts only Ollama/OpenAI-compatible descriptors with absolute HTTP(S) endpoints; non-cloud descriptors must point at loopback and cloud consent is a strict boolean. `secret_ref` accepts only an environment-variable name. Registration and capability discovery never read a secret or contact the endpoint. Default tests passed 10 tests with the listener skipped; the opt-in HTTP suite passed all 11 tests and verifies the provider guardrails.

Applied the permanent cross-account continuation protocol. The stored next-session prompt is now regenerated at meaningful verified milestones, user-requested handoffs, and before usage exhaustion, and embeds the dedicated recursive protocol that every future account must preserve.

Configured the official GitHub `origin` and verified with `git ls-remote --heads` that it had no branch heads before first publication. Added permanent GitHub continuity, safe-push, and remote-verification requirements to the handoff checkpoints.
