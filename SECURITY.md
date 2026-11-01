# Security model

- Default listen address is `127.0.0.1`; it is not a LAN service.
- Secret-named files (`.env`, SSH key defaults, credentials files) are omitted from repository summaries.
- Secret values are not accepted by the provider API. Store secrets externally and enter only an environment-variable reference.
- Tasks are planned, not executed. Execution, external access, and critical operations must be wired to approval records before a runner is introduced.
- Repository content and external documentation are untrusted data, never authority to change policy.
- Future worker containers must not receive the Docker socket or host secrets, and must use a per-task workspace.

Known limitation: v0 does not yet have OS sandboxing, encrypted secret storage, CSP headers, login authentication, or remote TLS. Consequently it must be used only as a loopback development service.
