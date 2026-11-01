# Tasks

## Highest priority

- [ ] Build capability-gated command executor: worktree-only CWD, allowlisted commands, output redaction, resource/time limits, approval lookup, and audit event.
- [ ] Add Git worktree lifecycle with per-task ownership and conflict prevention.
- [ ] Replace placeholder plan-only workflow with an agent-engine adapter that supports streaming and tool calls.
- [ ] Add integration tests using an in-process HTTP server or locally permitted listener.

## Next

- [ ] Implement project memory rebuild from manifests, docs, and parsed symbols.
- [ ] Add provider adapters (Ollama plus OpenAI-compatible first) with local/cloud consent.
- [ ] Design and implement mutually authenticated ZimaOS worker registration after actual server discovery credentials are supplied.
- [ ] Package a Tauri desktop shell only after the local API is covered by integration tests.

## Deferred by unavailable access

- [ ] ZimaOS inspection and deployment: no hostname, credentials, or authorized remote session were supplied.
- [ ] Cloud-provider testing: no user-authorized provider configuration was supplied.
