# Backend implementation matrix

## Master mission review — 2026-11-19

Current source9e3f6fd includes the November17 Mac process sandbox, Finder-scoped agent and full-task delivery; older claims of no local OS boundary are historical. JARVIS coding remains disabled and its Linux executor remains an unaccepted operator-only prototype. Memory now shares write admission, clears edited proof, verifies retrieval provenance and atomically promotes under the shared project cap.303Python discovered/298pass/5skip;14new cases. New `verification` listing field is additive. No OpenJarvis runtime dependency, common four-method task backend, general FTS5 ingestion, learned routing, unified trace/usage system or complete realistic ML acceptance has been implemented. See the roadmap/test report; the mission and remote deployment remain partial.

## Mission 1B delta

| Area | Current classification |
| --- | --- |
| Worker replay/rotation/protocol | Implemented, unit/HTTP tested, real Qwen workflow 19/19; remote private HTTPS unverified |
| Offline encrypted recovery | Implemented and locally restored with Git/history/ledger/config + revoked authority; limited to 64 MiB, larger-data recovery incomplete |
| OS execution boundary | Operator-only prototype and contract/negative tests implemented; actual Linux enforcement and backend broker integration incomplete; production coding disabled |
| Storage enforcement | Admission/margins/bounded inventory/DB page cap implemented and tested; no total filesystem quota, actual server accounting unverified |
| Release/preflight/acceptance | Image metadata pinned and static/mock/read-only tooling tested; no image/container/service build/install/runtime verification |
| SSH/target infrastructure | Empty local agent diagnosed; new diagnostic blocked by auto-review; no fresh JARVIS facts |
| Deployment/publication | Approval required; not installed, served, ACL-applied, published or complete |


AFK audit starting at implementation c5e3415 / checkpoint 4a3ea1d. Classifications describe working code, not remote deployment evidence.

| Area | Starting classification | Action in this session |
| --- | --- | --- |
| Auth, sessions, approvals | Complete and locally verified; single owner only | Preserve boundaries; separate inference-worker authority from owner |
| API validation/errors/version | Present but incomplete | Proxy contract, readiness, lifecycle and exact error handling |
| Conversations/history/search/retry/stop | Complete and locally verified | Preserve ordering/resume cursors and test worker transport |
| Projects/context/memory | Present; bounded local functionality | Keep evidence-backed memory and scope; no speculative vector database |
| Task/round/tool/worktree/Git | Present, substantial regression coverage | Preserve exact approvals; production execution disabled until containment is approved |
| Persistence/migrations/ledger | Present and locally verified | Add durable inference jobs, transactional claims and non-replay recovery |
| Provider/discovery/streaming | Present; Ollama/OpenAI-compatible local adapters | Add restricted outbound-polling Mac worker; no public Ollama port |
| Cancellation/timeouts | Present, incomplete stalled-stream coverage | Abort silent provider sockets and leased inference jobs |
| Diagnostics/backup/restore | Present and locally verified | Add readiness and deployment-safe bounded maintenance controls |
| Tailscale Serve | Missing proxy compatibility; approval-gated infrastructure | Implement exact trusted loopback proxy contract and secure cookies |
| Mac inference from JARVIS | Missing | Outbound worker protocol; fixed local Ollama allowlist, scoped token, leases and limits |
| Native client | Present with known read-only editor/command-runner limits | Align model location/status/worker API and test actual client where practical |
| Service/logging/resource deployment | Missing / external approval required | Prepare reviewed templates/preflight; no persistent infrastructure changes |
| OS-level execution/egress sandbox | Missing | Do not claim containment; fail closed for deployment execution mode |
| Remote HTTPS/ACL/storage acceptance | Blocked by explicit infrastructure approval | Prepare exact commands/proposals and record residual checks; no automatic deployment |

Mac inference, JARVIS control plane and private Serve HTTPS remain the intended architecture. New worker opens outbound connections to the approved control plane and fixed loopback Ollama only; it never opens an inbound Mac listener. Remote deployment, Serve/ACL/service/directory changes remain unexecuted.

## Final local classification

| Area | Final classification / evidence |
| --- | --- |
| Auth/API/conversations/persistence/ledger/context/memory | Complete for the implemented single-owner local scope; Python regressions, migrations, recovery, snapshots/restore and client checks pass |
| Coding tools/worktrees/approvals/tests | Complete for trusted local fixtures; real Qwen patch/test/completion proof passes. OS containment missing; remote execution deliberately disabled |
| Mac inference bridge | Complete and locally verified, real worker proof plus native streaming/stop; remote cross-device HTTPS unverified |
| Cancellation/timeouts/lifecycle | Complete within cooperative process limits; stalled sockets, leases, stream IDs, signal shutdown and restart covered |
| Native integration | Verified for changed flows using rebuilt app; broader prior manual proof retained. Read-only files and approved command runner; editor/PTY absent |
| Browser authentication | Complete and manually verified: invalid/valid login, cookie session, sign-out and disabled execution controls |
| Backup/resource diagnostics | Complete for own-data SQLite snapshots and bounded measurement; unattended schedule/full repository disaster recovery absent |
| Deployment/logging/monitoring | Templates/preflight complete and statically tested; actual container/version/resource behavior blocked by approval/access |
| Remote HTTPS/ACL/storage | Blocked by external approval/access; exact local review queue prepared, no installation performed |
| OS sandbox/egress/hard quota/multi-user auth | Missing; not represented as implemented or secure by worktree path checks |
