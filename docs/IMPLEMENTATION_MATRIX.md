# Backend implementation matrix

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
