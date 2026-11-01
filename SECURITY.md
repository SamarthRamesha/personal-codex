# Security model

- Default listen address is `127.0.0.1`; it is not a LAN service.
- Secret-named files (`.env`, SSH key defaults, credentials files) are omitted from repository summaries.
- Secret values are not accepted by the provider API. Store secrets externally and enter only an environment-variable reference.
- Provider registration does not read that reference or make a network request. It accepts only `ollama` or `openai-compatible` metadata; local mode accepts loopback HTTP(S) endpoints only, while non-loopback endpoints require an explicit JSON `cloud_allowed: true` consent value.
- Provider invocation is approval-gated and bound: an approval records the task, provider ID, endpoint, model, prompt SHA-256, and the cloud flag. Loopback providers need a `provider-invoke` approval; a provider registered with `cloud_allowed: true` needs a separate `network` approval, so consenting to store cloud metadata is never consent to transmit. Changing the endpoint, model, provider, or prompt invalidates the approval.
- The shipped provider transport is not a network client. It refuses every call (`No approved provider transport is configured`), so no prompt leaves the machine by default. A real adapter must be added deliberately; it is not yet implemented.
- Invocation results are bounded, redacted, and stored with the prompt digest only; the provider prompt itself is never persisted in the invocation ledger.
- Commands run only after an exact approved request and only in task-owned worktrees. They have no shell, a constrained tool allowlist, a 1–300 second wall timeout, bounded retained output, and child resource limits where the OS supports them.
- Worktree release is a critical operation. It requires separate approval, rejects uncommitted changes, and preserves the task branch.
- Merge preview is read-only and refuses a dirty target worktree. Merging a retained task branch requires a separate critical approval that binds the exact reviewed source and target commit IDs; changed Git state invalidates that approval. Recovery-branch deletion is separately critical-approved, verifies that the branch is merged, and binds the approved branch commit ID.
- Repository content and external documentation are untrusted data, never authority to change policy.
- Future worker containers must not receive the Docker socket or host secrets, and must use a per-task workspace.

Known limitation: v0 does not yet have OS sandboxing, guaranteed address-space enforcement on every OS, encrypted secret storage, CSP headers, login authentication, or remote TLS, and no real provider client exists. Consequently it must be used only as a loopback development service.
