# Tasks

## Mission 1 priorities — 2026-11-07

- [x] Reconcile actual checkout and remote stabilization branch; preserve untracked diagnostic and historical main.
- [x] Establish 156-test baseline after incorporating remote test fix; extend to 177 discovered tests.
- [x] Discover Mac Tailscale and installed Ollama models without downloads.
- [x] Build native Tauri/React/TypeScript client with guarded backend transport, streaming chat and a coherent coding review slice.
- [x] Add owner authentication, sessions, request hardening and private TLS listener policy.
- [x] Close chat auto-cloud-consent and default-enabled external-gateway gaps.
- [x] Add storage diagnostics, verified bounded snapshots and no-overwrite restore tests.
- [x] Prove a genuine installed local-model coding workflow and restart persistence.
- [x] Test actual native UI, owner-token failure/success and TLS identity refusal.
- [ ] Establish SSH authentication for `<ssh-user>@<server-tailscale-ip>` without putting credentials in chat or Git.
- [ ] Run read-only host inventory; measure actual CPU/RAM/GPU/filesystem/services/model storage.
- [ ] Prepare a reviewed least-privilege server deployment; obtain approval before installations/configuration/credential use or server writes.
- [ ] Verify 200 GB free reserve and 75 GB total owned-storage budget including model storage; no backup traversal or cleanup.
- [ ] Deploy authenticated TLS on the actual Tailscale interface; test at home and remotely.
- [ ] Complete genuine native-to-JARVIS coding acceptance and hardware performance measurements.
- [ ] Add OS execution/egress isolation, bounded global agent scheduling, backup supervision and automated UI coverage.
- [ ] Extend native editor/PTY, memory/Git controls and conversation management; add signing/notarization and reviewed update strategy.
- [ ] Continue Missions 2 and 3 after the actual remote foundation is accepted.

Memory promotion must always retain explicit approval; ordinary retrieval/configuration is not model training. Do not implement the old “automatic promotion” idea as automatic storage.

## Historical checklist follows

Preserved for continuity; the current priorities and implementation evidence above supersede stale unchecked entries.

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

- [x] Implement the bounded multi-round loop: send redacted test output back to the provider, cap rounds/time/operations, and require a fresh approval per proposal.
- [x] Add streaming response support.
- [ ] Add audited provider-native tool-call handling.
- [x] Add a bounded repository context engine (manifest, docs, symbols, ranking, digest).
- [x] Add a project-memory foundation with CRUD and credential rejection.
- [x] Add a live-provider diagnostic harness and deterministic coverage for it.
- [x] Add evidence-backed memory promotion with provenance, staleness and bounded retrieval.
- [x] Add bounded streaming for Ollama with cancellation and validation.
- [x] Add provider health/latency metadata and secret-shape error redaction.
- [ ] Run a live Ollama round on the owner's Mac and record the real failure modes.
- [x] Add OpenAI-compatible SSE streaming.
- [x] Add provider failure classification and safe read-only retry.
- [x] Add evidence-derived completion summary proposals.
- [ ] Add provider-native tool calls.
- [ ] Promote verified memory entries automatically from completed rounds.
- [x] Add restart recovery for interrupted rounds: they are marked `interrupted`, their proposals are closed, and the task returns to `needs-another-round`.
- [x] Add a persisted cancellation checked between tool operations, with partial-result preservation and skipped-operation recording.
- [x] Persist an operation-level ledger with timing, applied flag and file hashes; mark running rows interrupted on restart.
- [ ] Run one live Ollama agent cycle on the owner's Mac with a locally pulled model (requires the owner's machine and an installed Ollama).
- [ ] Implement project memory rebuild from manifests, docs, and parsed symbols.
- [ ] Design and implement mutually authenticated ZimaOS worker registration after actual server discovery credentials are supplied.
- [ ] Package a Tauri desktop shell only after the local API is covered by integration tests.
- [x] Stop a running test command on cancellation: SIGTERM, then SIGKILL after a 1.5 s grace, partial output preserved, exit code 130.
- [x] Stream persisted task events to the dashboard with resumable ids (`Last-Event-ID`).
- [x] Review a pending proposal as a unified diff bound to current file digests, with stale detection.
- [x] Add bounded, `.gitignore`-aware local repository search.
- [x] Send restrictive security headers (CSP, nosniff, no-referrer, frame denial, no-store) on every response.
- [ ] Add optional browser automation (Playwright) UI tests once a browser runtime is available in the target environment.

## Deferred by unavailable access

- [ ] ZimaOS inspection and deployment: no hostname, credentials, or authorized remote session were supplied.
- [ ] Live cloud-provider testing: no user-authorized provider credentials were supplied.
