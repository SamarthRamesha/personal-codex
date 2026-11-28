# Current implementation and remaining work

Updated 28 November 2026. See [current acceptance and limits](PRODUCT_COMPLETION.md).

| Area | Implemented and checked | Remaining |
|---|---|---|
| Conversations | Persisted history/search, streaming/stop and regeneration; actual candidate restart, pin/rename/archive/restore checked. Context disclosure/project filter/delete have regression coverage | Broader desktop acceptance and actual private remote HTTPS acceptance |
| Coding | Project task creation, scoped worktrees and approvals, proposal diffs, live operation ledger, check output, repair, exact Git delivery after a reviewed worktree commit, and explicit full-task resume | Broader stacks, editor/PTY, complex blank-project generation; real 9B bounded CLI/web fixtures now pass |
| Project readiness | Read-only report of manifests, dependency and toolchain state, declared checks, install commands, and declared dev scripts and ports. The workspace reports its own dependency markers and supports refresh after setup. | Detection covers Node, Python, Rust and Go. Task panels support exact reviewed locked npm installation and owned plain-Node previews. Other managers/frameworks remain terminal-managed. The offline launcher's `--doctor` reports platform, app, ports, models, disk and database integrity before a launch. |
| Reviewed installation | Exact npm lock v2/v3 registry packages, SHA512, disabled scripts, private staging, cancellation/restart preservation; actual desktop install passed | Existing dependency replacement, other managers/workspaces/native-addon setup |
| Managed previews | Reviewed Node entry, inherited loopback socket, bounded logs, owner stop and backend-death cleanup; actual desktop page checked | Framework adapters, hot reload/cache writes, cooperating services, WebSocket acceptance |
| Progress | Exact bounded proposal cycles1–3, content-progress resets and context bounds | Semantic/changing-content loop detection and unified traces |
| Memory/references | Project memory panel with owner notes, explicit evidence-backed promotion and removal, selected-excerpt FTS5 with hashes/chunks/removal | Broader retrieval evaluation |
| Models | Existing local models with an automatic offline provider seed, explicit metadata unknowns, measured calls, no cloud fallback; any installed Ollama tag can be named explicitly, with the vetted Qwen pair as default | Routing benchmarks and broader capability acceptance |
| ML | Real-model existing-project repair with independent tests, artifact checks and a frontend | General complete-project generation and production fairness/quality guarantees |
| Mac opening actions | Native catalogue/Finder selection, exact expiring one-use review; tests/build pass | Actual opening/Finder acceptance; search, proposal and cancellation visually checked |
| Mac automation preview | Native helper, bounded window scopes, reviewed actions, local planner, optional capture/OCR, owned synthetic self-check; 42 helper checks, 17 Rust checks plus one ignored, and candidate build pass | Manual OS permission; actual native/browser/capture and natural-language-to-real-UI acceptance; no universal app support |
| Mac inference worker | Outbound polling, scoped authority, leases/replay/rotation/cancel tests and earlier real-model fixture | Persistent installation and actual JARVIS HTTPS lifecycle tests |
| API container | Exact282b90d source passes17 checks in a disposable Linux guest | Target-specific image/identity/importer/runtime proof; no coding-executor certificate |
| JARVIS management | Existing owner dashboard and Custom App route observed read-only | Field preservation, image delivery, exact storage/ownership, explicit installation approval |
| Private access | Strict proxy/TLS/auth code and reviewed policy tooling | Family443/routes/shares/emergency inventory, live policy confirmation/vendor tests, separate exact Serve/policy approvals |
| Recovery/storage | Bounded snapshots,64 MiB encrypted recovery, admission and DB caps | Production-scale streaming recovery, hard quota, key custody/schedule/off-device acceptance |
| Distribution | Local optimized ad-hoc signed builds; pinned dependency lockfiles | Signed/notarized installer, trusted updates and broader UI regression |

## Latest verification

- Full Mac HTTP backend: 510 discovered, 505 passed, five optional/platform skips.
- Frontend: 101 checks; TypeScript/Vite build passed. Rust: 17 passed, one optional model test ignored.
- Integration CI #128 and #129 passed all jobs, including scripted coding, resume, actual contained npm and preview lifecycle tests. CI #131 also passed the packaged candidate.
- Installed qwen3.5:9b existing-project repair passed in 49.23 seconds; supplied-baseline web implementation passed in 180.81 seconds with unchanged independent tests, locked dependency installation and independent preview HTTP checks.
- The generated browser calculator returned 5 for 2+3 and 1 for -2+3. Actual isolated desktop startup, settings, opening review/cancel, dependency installation, preview readiness and chat controls were exercised.
- Candidate Accessibility and key-event grants remain unavailable. Native UI automation, product browser helper and capture/OCR remain owner-only acceptance gates. Approved preview and existing permissions were preserved.
- JARVIS deployment and stable-main recovery remain separate authorization gates.

See [documentation index](README.md), [current evidence](PRODUCT_COMPLETION.md), [progress guards](AGENT_PROGRESS_GUARDS.md), [document search](PROJECT_DOCUMENT_SEARCH.md) and [deployment](../DEPLOYMENT.md). These current pages supersede older milestone status tables.
