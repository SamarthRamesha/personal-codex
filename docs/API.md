# API v1 integration contract

The HTTP surface retains `/api/` routes for compatibility; `/api/connection` and authenticated `/api/ready` report `api_version: 1`. There is one owner, no multi-user role model. JSON mutations have bounded object bodies. Error replies are JSON with a controlled `error` string; the native client must not replay mutations automatically.

| Route | Authority | Contract |
| --- | --- | --- |
| `GET /api/health` | None, valid Host/origin | Liveness only; does not certify inference/storage readiness |
| `GET /api/ready` | Owner/session | 200 only if DB, measured storage reserve/budget, accepting state and all enabled worker models are ready; otherwise 503 |
| `GET /api/connection` | Owner/session | API version, secure transport, explicit public origin, execution mode and capabilities |
| `POST /api/session` | Valid owner token in `{token}` | HttpOnly, SameSite=Strict one-hour session; Secure behind exact configured Serve proxy; throttled invalid login |
| `DELETE /api/session` | Owner/session | Revoke session and expire cookie |
| `GET /api/inference/status` | Owner/session | Worker presence, installed allowlist and job counts; no prompts, credentials or lease values |
| `GET/POST /api/providers` | Owner/session | Existing local adapters plus `kind: mac-worker`; worker provider accepts exact `model`, no endpoint, secret reference or cloud flag |
| `GET /api/providers/{id}/models` | Owner/session | Real reported installed worker allowlist, or adapter discovery |
| `GET/POST /api/conversations` | Owner/session | Persisted chats; optional project/provider/model, search through query parameters |
| `GET /api/conversations/{id}` | Owner/session | Conversation with ordered persisted messages |
| `POST /api/conversations/{id}/messages` | Owner/session | `{content, provider_id?}` → 202 with user and assistant message IDs; no cloud chat fallback |
| `GET /api/conversations/{id}/messages/{message}/stream?after={seq}` | Owner/session | Persisted SSE chunks, `done` terminal; resume only after committed cursor; missing message returns JSON 404 before SSE headers |
| `POST /api/conversations/{id}/messages/{message}/stop` | Owner/session | Stop current inference; partial text remains display-only |
| `POST /api/conversations/{id}/regenerate` | Owner/session | New explicitly requested attempt, never background invocation retry |
| `GET/POST /api/projects`, `GET /api/projects/{id}/files`, `/file?path=…`, `/search?q=…` | Owner/session | Explicit roots and contained, bounded, secret-filtered files/search; symlinks excluded |
| `POST /api/tasks`, `GET /api/tasks/{id}/…` | Owner/session | Plans, workspace, events, agent/rounds/report/diff, execution evidence and operation ledger |
| `PATCH /api/approvals/{id}` | Owner/session | One atomic pending → approved/rejected decision, bound operations revalidated at execution |
| `POST /api/tasks/{id}/workspace-request`, `/workspace`, `/execution-request`, `/execute`, `/agent/round/request`, `/agent/round/plan`, `/agent/round/execute` | Owner/session | Exact separate approvals; code proposal, patch, execution/worktree/Git operations refused in disabled profile |
| `POST /api/tasks/{id}/cancel`, `/agent/round/cancel` | Owner/session | Cooperative cancellation with late model/tool results rejected |
| `GET /api/diagnostics`, `POST /api/maintenance/backup` | Owner/session | Own-data inventory only, verified private SQLite snapshots; concurrent snapshot refusal; no cleanup |

The server routes remain the authority for the full legacy task, memory, release, merge and deletion surface. This table highlights client integration; it is not a generated OpenAPI specification.

## Scoped outbound worker protocol

Worker bearer token is **distinct** from the owner token. It cannot read projects/chats/diagnostics, approve changes, create sessions or act as owner. Owner credentials cannot substitute for a worker credential.

1. `POST /api/worker/poll` with exactly `{models: [installed exact names]}` reports presence, returning `{job: null}` or `{job: {id, model, prompt, prompt_sha256, deadline, lease}}`.
2. `POST /api/worker/jobs/{uuid}/heartbeat` with exactly `{lease}` returns `status`, `seq`, `deadline`. One worker generation at a time; 15-second leases, at most four active jobs.
3. `POST /api/worker/jobs/{uuid}/chunks` with `{lease, seq, text?, done?, error?}` appends ordered text. Sequence starts at one; retrying the identical last payload is idempotent. A conflicting duplicate, missing sequence or late completion is rejected. Lease failure returns 403; invalid state/body returns 409.
4. Heartbeat observes cancellation; control loss aborts local provider work. A job is never re-leased or silently invoked again. Restart marks in-flight jobs interrupted and resets worker presence.

Prompt limit 100,000 UTF-8 bytes; response limit 200,000 bytes; chunk limit 4,000 characters; timeout 2–300 seconds (normally 180); presence TTL 30 seconds; 10,000 retained metadata rows maximum. Retention exhaustion fails closed and needs reviewed archival, with no automatic deletion. Worker jobs are temporary prompt/response transport; payloads clear after completion consumption/cancellation/recovery, while normal conversation and invocation history persists. SQLite free pages/backups can retain historical bytes; this is not secure erasure.

The Mac process polls only the explicit private HTTPS backend and a fixed loopback Ollama endpoint. It validates job schema, model allowlist and prompt digest, and has no command, arbitrary proxy, filesystem or download protocol. Chunk transport retries do not repeat model inference.

## Trusted Serve boundary

Configure an exact `PERSONAL_CODEX_PUBLIC_ORIGIN=https://host.tailnet.ts.net` only with owner authentication, HTTP loopback listener, disabled repository execution and explicit project roots. Forwarded metadata is accepted only from loopback with exact Host/X-Forwarded-Host and HTTPS scheme. Duplicate security/proxy headers, cross-site origins and standard Forwarded are rejected. Forwarded identity does not authenticate requests. Direct loopback diagnostics remain HTTP. Local processes remain in the trust boundary; this is not a cryptographic proxy identity check.

Native `api_stream` carries a stream ID; scoped `cancel_stream` prevents stale cleanup from cancelling a successor. Both browser and native SSE parsers cap frames at 64 KiB and release transport/listeners on abort or malformed frames. Native HTTPS verification has no insecure bypass.
