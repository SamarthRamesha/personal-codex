# Tasks

## Highest priority

- [x] Establish permanent cross-account continuation protocol and regenerate the ready-to-use prompt after verified milestones.
- [x] Build capability-gated command executor: worktree-only CWD, allowlisted commands, output redaction, timeout, approval lookup, and audit event.
- [x] Add basic Git worktree lifecycle with per-task ownership.
- [x] Add clean workspace release/recovery controls and resource limits beyond timeout.
- [x] Add explicit user-approved branch merge, conflict reporting, and recovery-branch deletion controls.
- [x] Add provider metadata validation and capability discovery without secret access or network I/O.
- [x] Connect the injected transport seam to approval-gated invocation endpoints, with bounded redacted responses, a digest-keyed ledger, and audit events.
- [x] Add browser-free dashboard contract tests covering the approval/workspace/command/merge/provider controls.
- [ ] Replace placeholder plan-only workflow with an agent-engine adapter that supports streaming and tool calls.

## Next

- [ ] Implement a real Ollama HTTP transport behind the existing injected seam, still requiring approval and still refusing non-loopback endpoints without `network` consent. Cover it with a local stub server test before any live call.
- [ ] Implement an OpenAI-compatible transport that reads its key only from the named environment variable at call time and never persists or logs it.
- [ ] Add streaming response support and audited tool-call handling to the invocation ledger.
- [ ] Implement project memory rebuild from manifests, docs, and parsed symbols.
- [ ] Design and implement mutually authenticated ZimaOS worker registration after actual server discovery credentials are supplied.
- [ ] Package a Tauri desktop shell only after the local API is covered by integration tests.
- [ ] Add optional browser automation (Playwright) UI tests once a browser runtime is available in the target environment.

## Deferred by unavailable access

- [ ] ZimaOS inspection and deployment: no hostname, credentials, or authorized remote session were supplied.
- [ ] Live cloud-provider testing: no user-authorized provider credentials were supplied.
