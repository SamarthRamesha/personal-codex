# Security model

- Default listen address is `127.0.0.1`; it is not a LAN service.
- Secret-named files (`.env`, SSH key defaults, credentials files) are omitted from repository summaries.
- Secret values are not accepted by the provider API. Store secrets externally and enter only an environment-variable reference.
- Commands run only after an exact approved request and only in task-owned worktrees. They have no shell, a constrained tool allowlist, a 1–300 second wall timeout, bounded retained output, and child resource limits where the OS supports them.
- Worktree release is a critical operation. It requires separate approval, rejects uncommitted changes, and preserves the task branch.
- Merge preview is read-only and refuses a dirty target worktree. Merging a retained task branch requires a separate critical approval that binds the exact reviewed source and target commit IDs; changed Git state invalidates that approval. Recovery-branch deletion is separately critical-approved, verifies that the branch is merged, and binds the approved branch commit ID.
- Repository content and external documentation are untrusted data, never authority to change policy.
- Future worker containers must not receive the Docker socket or host secrets, and must use a per-task workspace.

Known limitation: v0 does not yet have OS sandboxing, guaranteed address-space enforcement on every OS, encrypted secret storage, CSP headers, login authentication, or remote TLS. Consequently it must be used only as a loopback development service.
