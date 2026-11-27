# Current implementation and remaining work

Updated 27 November 2026.

| Area | Implemented and checked | Remaining |
|---|---|---|
| Conversations | Persisted history and search, streaming and stop, regeneration of the newest answer with the selected local model, context disclosure, project filter, and pin/rename/archive/restore/delete | Installed-model acceptance on the M3 and actual private remote HTTPS acceptance |
| Coding | Project task creation, scoped worktrees and approvals, proposal diffs, live operation ledger, check output, repair, exact Git delivery after a reviewed worktree commit, and explicit full-task resume | Broader stack support, dependency installation and dev-server lifecycle, editor/PTY, complex blank-project generation, hands-on M3 acceptance |
| Project readiness | Read-only report of manifests, dependency and toolchain state, declared checks, install commands, and declared dev scripts and ports. The workspace reports its own dependency markers and supports refresh after setup. | Detection covers Node, Python, Rust and Go. The owner manages install and development-server commands in a dedicated terminal. |
| Progress | Exact bounded proposal cycles1–3, content-progress resets and context bounds | Semantic/changing-content loop detection and unified traces |
| Memory/references | Project memory panel with owner notes, explicit evidence-backed promotion and removal, selected-excerpt FTS5 with hashes/chunks/removal | Broader retrieval evaluation |
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

- Linux backend HTTP tier: 466 discovered, 462 passed, four skipped.
- Frontend: 95 passed across 18 files. TypeScript and Vite production build passed.
- Integration CI #115 passed backend, frontend and native macOS, including scripted full-task delivery and native bundling. Interactive Mac acceptance is pending.
- A browser test on a disposable Git project exercised review, failure, repair, delivery, and persisted results after backend restart with scripted inference.
- The owner reports JARVIS online. The private deployment plan remains ready for authorized target review.

See [documentation index](README.md), [ML evidence](ML_WORKFLOW_ACCEPTANCE.md), [progress guards](AGENT_PROGRESS_GUARDS.md), [document search](PROJECT_DOCUMENT_SEARCH.md) and [deployment](../DEPLOYMENT.md). Historical milestones remain in Git history and the changelog; this page supersedes their old status tables.
