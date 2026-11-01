# Changelog

## 0.1.0 — 2026-11-01

- Created local-first Personal Codex control-plane foundation.
- Added SQLite persistence, project registration, task plans, approvals, provider metadata, and dashboard.
- Added security-oriented repository filtering and unit coverage.
- Added approval-gated task workspaces and exact command execution boundary.
- Added dashboard controls to inspect and decide approvals, request isolated workspaces, request exact command approval, and inspect task events/output.
- Added disposable, opt-in HTTP integration coverage for the approval-gated workspace and command lifecycle.
- Added resource-limited execution and critical-approval clean-workspace release with retained recovery branches.
- Added read-only merge previews, conflict reporting, critical-approved merges, and separately approved recovery-branch deletion. Approval records bind the reviewed Git commit IDs.
- Added strict provider metadata validation and capability discovery for future Ollama/OpenAI-compatible adapters, without secret access or provider network I/O.
- Added approval-gated provider invocation: bound approvals over task, provider, endpoint, model, prompt digest, and cloud flag; a separate `network` approval for cloud-consented providers; a fail-closed default transport; and a bounded, redacted invocation ledger.
- Added dashboard provider-invocation controls and a provider-response ledger.
- Added browser-free dashboard contract tests for element IDs, button wiring, routed API paths, gated controls, and local-only assets.
