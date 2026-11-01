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
- [x] Implement a real Ollama HTTP transport behind the injected seam, approval-gated, loopback-only without cloud consent, verified against a local stub server.
- [x] Implement an OpenAI-compatible `/chat/completions` transport whose key is read only from the named environment variable at call time.
- [x] Harden the shared transport: no redirects, no proxy-env use, bounded timeout/size, sanitised errors, missing-credential failure before sending.
- [x] Implement the first bounded developer-agent cycle: strict allowlisted tool-call schema, approval-gated patch application in the task worktree, and test-result recording.
- [x] Add the agent lifecycle API and dashboard proposal/execute controls.
- [ ] Replace placeholder plan-only workflow with a multi-round agent engine that feeds bounded test results back to the provider.

## Next

- [ ] Implement the bounded multi-round loop: send redacted test output back to the provider, cap rounds/time/operations, and require a fresh approval per proposal.
- [ ] Add streaming response support and audited provider-native tool-call handling.
- [ ] Run one live Ollama agent cycle on the owner's Mac with a locally pulled model (requires the owner's machine and an installed Ollama).
- [ ] Implement project memory rebuild from manifests, docs, and parsed symbols.
- [ ] Design and implement mutually authenticated ZimaOS worker registration after actual server discovery credentials are supplied.
- [ ] Package a Tauri desktop shell only after the local API is covered by integration tests.
- [ ] Add optional browser automation (Playwright) UI tests once a browser runtime is available in the target environment.

## Deferred by unavailable access

- [ ] ZimaOS inspection and deployment: no hostname, credentials, or authorized remote session were supplied.
- [ ] Live cloud-provider testing: no user-authorized provider credentials were supplied.
