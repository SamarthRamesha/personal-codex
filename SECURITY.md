# Security model

## Current security boundary — 2026-11-07

Read `docs/THREAT_MODEL.md` for the current threat matrix and residual risks. The inventory below preserves prior work and is superseded where it describes authentication/TLS/CSP/streaming as absent.

The default entrypoint binds loopback. A remote bind is allowed only for an explicit Tailscale address with an owner token file and TLS certificate/key; wildcard/public/ordinary LAN binds fail before listening. No Tailscale/router/firewall settings are changed by this code. Sensitive APIs, streams and mutations require the configured owner token or valid expiring cookie. A deliberately unauthenticated loopback development mode remains available. Owner auth does not replace exact task approvals or OS isolation.

Token files must be owner-only regular files and are opened without following symlinks. Tokens never appear in request logs, browser storage or the database. Native disconnect drops credentials and backend data. Cookie sessions are hashed in memory, expire after one hour and are revoked on logout/restart; the long-lived bearer token is revoked by replacing its file and restarting. No multi-user authorization or encrypted credential store is implemented.

Host/Origin/Sec-Fetch checks, strict JSON/framing/body bounds, request timeouts and existing security headers defend the application boundary. Cloud chat refuses transmission instead of approving itself. The optional external gateway is disabled unless explicitly enabled and still requires network approval per task call. Default operation has no cloud fallback. Round cancellation prevents a late provider response from creating a runnable proposal.

**Execution limitation:** approved tests still execute host-accessible repository code. Command allowlisting, worktrees and digest approvals are not an OS filesystem/network sandbox. Do not claim arbitrary untrusted repositories are safe or deploy such execution alongside family backups until OS containment and egress policy are implemented and tested. No server changes were performed in this session.

- Default listen address is `127.0.0.1`; it is not a LAN service.
- Secret-named files (`.env`, SSH key defaults, credentials files) are omitted from repository summaries.
- Secret values are not accepted by the provider API. Store secrets externally and enter only an environment-variable reference.
- Provider registration does not read that reference or make a network request. It accepts only `ollama` or `openai-compatible` metadata; local mode accepts loopback HTTP(S) endpoints only, while non-loopback endpoints require an explicit JSON `cloud_allowed: true` consent value.
- Provider invocation is approval-gated and bound: an approval records the task, provider ID, endpoint, model, prompt SHA-256, and the cloud flag. Loopback providers need a `provider-invoke` approval; a provider registered with `cloud_allowed: true` needs a separate `network` approval, so consenting to store cloud metadata is never consent to transmit. Changing the endpoint, model, provider, or prompt invalidates the approval.
- Built-in adapters (`app/providers.py`) implement Ollama `/api/chat` (or `/api/generate`) and OpenAI-compatible `/chat/completions`. They use `http.client`, so proxy environment variables are ignored and redirects are never followed; a 3xx response is an error. Every call has a connection timeout, a 1 MB response cap, and sanitised, length-capped error text.
- The adapters independently re-check the endpoint: only absolute http(s) URLs without embedded credentials, and a non-loopback host is refused unless the provider is cloud-consented. A transport therefore cannot be redirected to an external host by a loopback configuration.
- An OpenAI-compatible credential is read from its environment variable inside the transport at call time, used only in the `Authorization` header, and never returned, logged, or stored. A cloud provider with no secret reference is refused. Missing credentials fail before any request is sent.
- An injected transport overrides the built-ins for offline or deterministic operation; setting it to `unavailable_provider_transport` restores a hard fail-closed service.
- Invocation results are bounded, redacted, and stored with the prompt digest only; the provider prompt itself is never persisted in the invocation ledger.
- Model output never executes directly. A proposal is validated against a closed tool schema and applied only after an approval bound to the proposal digest, workspace branch/path, and reviewed file hashes. Paths are confined to the task worktree; absolute paths, `..`, ignored directories, secret-named files, and symlink escapes are refused.
- `apply_patch` requires exactly one match of the reviewed text and re-verifies the reviewed SHA-256, so a file changed after approval fails instead of being overwritten. Execution stops at the first failure, and a proposal can execute at most once.
- Commands run only after an exact approved request and only in task-owned worktrees. They have no shell, a constrained tool allowlist, a 1–300 second wall timeout, bounded retained output, and child resource limits where the OS supports them.
- Each agent round has its own two approvals: the provider invocation bound to task, provider, endpoint, model, prompt digest, and round number; and the proposal bound to task, round, workspace branch/path, proposal digest, and prompt digest. A previous round's approval can never authorize a later round's proposal.
- Round execution recomputes the proposal digest from stored operations, re-verifies reviewed file hashes immediately before applying, and refuses a stale or already-executed round. Duplicate provider responses and already-reviewed proposal digests are refused, so an identical re-proposal cannot silently run again.
- Round completion is server-verified against recorded evidence (a zero-exit test command and an approved file change in the latest executed round). Model text cannot mark a task complete; a rejected claim is recorded as `rejected-completion`.
- Feedback sent back to the provider is redacted and capped (2 000-character output tail, 60-path workspace listing, bounded history), so rounds cannot stream unbounded repository content or logs to an endpoint. Cloud endpoints still require the separate `network` approval per invocation.
- Rounds are capped (default 3, `PERSONAL_CODEX_MAX_ROUNDS` 1–10), time-capped at 1 800 seconds per task, limited to 8 operations, and can be cancelled; cancellation invalidates the pending proposal.
- Cancellation is persisted and bound to the active round; a cancelled round's approval is revoked, completed operations are preserved, and remaining operations are never started.
- Each operation writes a ledger row before and after it runs. On restart, rows left `running` are marked `interrupted` and are never replayed; completed rows and their hashes are preserved.
- Cumulative prompt/response/test-output/context/invocation budgets are enforced before any provider call. Exhaustion stops the task, records the reason, and requires an explicit confirmed reset; no budget resets silently.
- Repository context is selected locally under byte caps and excludes `.gitignore`d paths, ignored directories, secret-named files, oversized files and symlinks that leave the workspace. It is rendered into the prompt as untrusted data, and the context API exposes only file metadata and a digest, never the stored prompt.
- Project memory rejects credential-like content, is bounded to 200 entries of 2,000 characters, and is presented to the model as possibly stale rather than as authority.
- Memory cannot enter prompts or storage from model prose: proposals require a passing round, are deduplicated, credential-checked, and stored only after an explicit user decision. Memory is labelled verified or possibly stale and never overrides repository files.
- Streaming accumulates bounded NDJSON and rejects malformed, unterminated, oversized, erroring or cancelled streams; only completed text can be validated, so partial output can never be approved or executed.
- Provider error bodies are scrubbed of secret-shaped strings before display or storage; model discovery reads no credential and is only invoked by the human-run diagnostic.
- The diagnostic script contacts a provider only when explicitly run, requires a named model, and never writes to a repository or the application database.
- Worktree release is a critical operation. It requires separate approval, rejects uncommitted changes, and preserves the task branch.
- Merge preview is read-only and refuses a dirty target worktree. Merging a retained task branch requires a separate critical approval that binds the exact reviewed source and target commit IDs; changed Git state invalidates that approval. Recovery-branch deletion is separately critical-approved, verifies that the branch is merged, and binds the approved branch commit ID.
- Repository content and external documentation are untrusted data, never authority to change policy.
- Future worker containers must not receive the Docker socket or host secrets, and must use a per-task workspace.

Known limitation: v0 does not yet have OS sandboxing, guaranteed address-space enforcement on every OS, encrypted secret storage, CSP headers, login authentication, or remote TLS. Provider streaming, provider-native tool calls, and project memory are not implemented. Consequently it must be used only as a loopback development service.

## Milestone 6 hardening (2026-11-02)

- Cancellation terminates the command's process group: SIGTERM first, SIGKILL after a 1.5 s grace period, so a cancelled test run cannot keep holding the workspace or keep writing output. A cancelled run is reported as `cancelled` with exit code 130 and can never be mistaken for a passing test.
- Partial output written before the stop is preserved for the audit trail, and the remaining operations are recorded as `cancelled` rather than silently skipped without a reason.
- The event stream is read-only, same-origin, bounded (500 events / 120 s), and cannot be used to write state. It emits only persisted event rows for the requested task.
- Diff review resolves each path through the workspace containment check, so it cannot read outside the worktree or a secret-named file; a changed digest marks the review stale and blocks execution of that approval.
- Repository search inherits the context engine's exclusions (`.gitignore`, secret names, symlinks, generated directories) and caps results, so it cannot be used as an oracle for secret content.
- Every response now sends a restrictive Content-Security-Policy (no inline script or style for the dashboard, `default-src 'none'` for JSON), `nosniff`, `no-referrer`, `X-Frame-Options: DENY` and `Cache-Control: no-store`.
- These controls are covered by tests; browser-level automated testing is still not available in the cloud workspace and is reported as pending rather than claimed.
