# Tasks

## Highest priority

- [x] Establish permanent cross-account continuation protocol and regenerate the ready-to-use prompt after verified milestones.

- [x] Build capability-gated command executor: worktree-only CWD, allowlisted commands, output redaction, timeout, approval lookup, and audit event.
- [x] Add basic Git worktree lifecycle with per-task ownership.
- [x] Add clean workspace release/recovery controls and resource limits beyond timeout.
- [x] Add explicit user-approved branch merge, conflict reporting, and recovery-branch deletion controls.
- [ ] Replace placeholder plan-only workflow with an agent-engine adapter that supports streaming and tool calls.
- [x] Add provider metadata validation and capability discovery without secret access or network I/O.
- [x] Add integration tests using an in-process HTTP server or locally permitted listener.
- [ ] Add UI tests for the approval/workspace/command workflow.

## Next

- [ ] Implement project memory rebuild from manifests, docs, and parsed symbols.
- [ ] Implement approval-gated provider invocation adapters (Ollama plus OpenAI-compatible first) with streaming, tool calls, and local/cloud consent. Metadata validation and an injected deterministic transport seam are complete.
- [ ] Design and implement mutually authenticated ZimaOS worker registration after actual server discovery credentials are supplied.
- [ ] Package a Tauri desktop shell only after the local API is covered by integration tests.

## Deferred by unavailable access

- [ ] ZimaOS inspection and deployment: no hostname, credentials, or authorized remote session were supplied.
- [ ] Cloud-provider testing: no user-authorized provider configuration was supplied.
