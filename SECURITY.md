# Security model

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
- Worktree release is a critical operation. It requires separate approval, rejects uncommitted changes, and preserves the task branch.
- Merge preview is read-only and refuses a dirty target worktree. Merging a retained task branch requires a separate critical approval that binds the exact reviewed source and target commit IDs; changed Git state invalidates that approval. Recovery-branch deletion is separately critical-approved, verifies that the branch is merged, and binds the approved branch commit ID.
- Repository content and external documentation are untrusted data, never authority to change policy.
- Future worker containers must not receive the Docker socket or host secrets, and must use a per-task workspace.

Known limitation: v0 does not yet have OS sandboxing, guaranteed address-space enforcement on every OS, encrypted secret storage, CSP headers, login authentication, or remote TLS. Provider streaming and tool-call execution are not implemented. Consequently it must be used only as a loopback development service.
