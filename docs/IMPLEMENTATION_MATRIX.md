# Current implementation and remaining work

Updated 24 November 2026. “Verified locally” does not mean deployed on JARVIS.

| Area | Implemented and checked | Remaining |
|---|---|---|
| Conversations | Persistence, history search, local models, streaming/stop/retry, native connection policy, attributed message-search hits, a context disclosure of what the next prompt can include, and pin/archive/restore/soft-delete controls with an archived view | Actual private remote HTTPS acceptance |
| Coding | Shared task lifecycle, scoped worktrees, approvals/diffs, contained Mac checks, repair, guarded delivery and explicit resume | Broader stacks, dependency installation and dev-server process lifecycle (readiness is reported, not executed), editor/PTY, blank-project complex generation |
| Project readiness | Read-only report of detected manifests, dependency state with its evidence, exact single install commands and declared dev scripts/ports; route, panel and 16 tests | Installing dependencies and running a dev server stay operator actions; only node/python/rust/go manifests are detected |
| Progress | Exact bounded proposal cycles1–3, content-progress resets and context bounds | Semantic/changing-content loop detection and unified traces |
| Memory/references | Evidence-bound memory, atomic promotion, selected-excerpt FTS5 with hashes/chunks/removal | Broader retrieval evaluation; no automatic private-data ingestion |
| Models | Existing local models, explicit metadata unknowns, measured calls, no cloud fallback | Routing benchmarks and broader capability acceptance |
| ML | Real-model existing-project repair with independent tests, artifact checks and a frontend | General complete-project generation and production fairness/quality guarantees |
| Mac opening actions | Native catalogue/Finder selection, exact expiring one-use review; tests/build pass | Visual opening acceptance, cross-app clicking/typing/reading and natural-language workflows |
| Mac automation preview | Native helper, bounded window scopes, reviewed actions, local planner, optional capture/OCR, owned synthetic self-check; 31 helper/13 Rust/17 frontend checks and preview build pass | Manual OS permission; actual native/browser/capture and natural-language-to-real-UI acceptance; no universal app support |
| Mac inference worker | Outbound polling, scoped authority, leases/replay/rotation/cancel tests and earlier real-model fixture | Persistent installation and actual JARVIS HTTPS lifecycle tests |
| API container | Exact282b90d source passes17 checks in a disposable Linux guest | Target-specific image/identity/importer/runtime proof; no coding-executor certificate |
| JARVIS management | Existing owner dashboard and Custom App route observed read-only | Field preservation, image delivery, exact storage/ownership, explicit installation approval |
| Private access | Strict proxy/TLS/auth code and reviewed policy tooling | Family443/routes/shares/emergency inventory, live policy confirmation/vendor tests, separate exact Serve/policy approvals |
| Recovery/storage | Bounded snapshots,64 MiB encrypted recovery, admission and DB caps | Production-scale streaming recovery, hard quota, key custody/schedule/off-device acceptance |
| Distribution | Local optimized ad-hoc signed builds; pinned dependency lockfiles | Signed/notarized installer, trusted updates and broader UI regression |

## Latest verification

- Backend:445 discovered, 441 passed, 4 skipped; 72.3 seconds (HTTP tier enabled, 24 November).
- Frontend:14 passed; TypeScript/Vite production build passed.
- Native:7 Rust tests passed; optimized app build passed. New Mac opening UI visual acceptance blocked by connector failure.
- Linux:17 checks for exact backend source282b90d, clean container stop/restart persistence; not JARVIS.
- JARVIS read-only check: MagicDNS resolves and dashboard 80 accepts TCP;443 and 8787 refuse connections. No credentials, HTTP requests, inference, SSH commands or target changes. Remote integration is **not accepted**.

See [documentation index](README.md), [ML evidence](ML_WORKFLOW_ACCEPTANCE.md), [progress guards](AGENT_PROGRESS_GUARDS.md), [document search](PROJECT_DOCUMENT_SEARCH.md) and [deployment](../DEPLOYMENT.md). Historical milestones remain in Git history and the changelog; this page supersedes their old status tables.
