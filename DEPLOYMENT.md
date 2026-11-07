# Deployment

## Current deployment contract — 2026-11-07

The native client and Mac backend are verified. JARVIS is **not deployed**. Authorized read-only SSH to `<ssh-user>@<server-tailscale-ip>` reached the host but the existing identity was rejected. The user's home directory is `/DATA`; do not treat that directory or its contents as application storage. No family backup directory was traversed and no server configuration was changed.

### Local Mac development

```sh
python3 app/server.py
# In another terminal:
cd desktop
npm ci
npm run tauri -- dev
```

The backend defaults to `127.0.0.1:8787` and `data/personal_codex.db`. This is an explicitly unauthenticated development mode. A packaged client connects to an already-running backend and does not silently launch or install a service. The existing browser dashboard is still served at the backend root.

For real local data, configure authentication:

```sh
mkdir -p data
python3 scripts/private_backend.py --create-token data/owner-token
PERSONAL_CODEX_TOKEN_FILE="$PWD/data/owner-token" python3 scripts/private_backend.py
```

The generator creates a 0600 file and refuses overwrite; it never prints the token. Enter its contents into the native app yourself, not in chat or logs. The native app holds the token in memory until disconnect/quit; only the backend URL is saved. Cookie login is available at `POST /api/session` with a JSON token, and logout at `DELETE /api/session`; a browser login form is not yet implemented.

### Read-only JARVIS discovery

The exact confirmed IP, hostname and SSH username are preserved only in local deliverable `PRIVATE_DEPLOYMENT_NOTES.md`, outside Git. Once SSH access works on the Mac, set `PC_SSH_USER` and `PC_SERVER_IP` to those confirmed values, then from the repository root:

```sh
ssh -o StrictHostKeyChecking=yes "${PC_SSH_USER}@${PC_SERVER_IP}" 'sh -s' < scripts/inspect_host.sh
```

Do not paste a password or private key into chat. Keep host-key verification on. The script prints CPU/instruction sets, OS/kernel, memory/load, filesystem metadata, accelerator devices, runtime availability, basic container names/images/ports, listeners/interfaces, Tailscale version/IP and local model metadata. It does not list or read `/DATA` contents, backup directories, environment variables or container secrets. It does not install, configure, clean or download anything.

Actual CPU, acceleration, filesystem, free storage, Docker/service support and models remain unknown. Choose deployment/inference technology only after this inventory. Current Tailscale observation: Mac Running; confirmed JARVIS online/active at `<server-tailscale-ip>`, MagicDNS `<server>.<tailnet>.ts.net`. No public probe, Serve/Funnel, router forwarding or ACL change was used.

### Reviewed private deployment (not yet authorized or executed)

Before deployment writes, prepare and obtain approval for the exact dedicated application directory, least-privilege account, repository roots, service supervision, certificate source and storage plan. Do not install a second inference engine or select a server model based on the Mac's model results. Do not configure or enable Tailscale HTTPS/Serve/Funnel/ACLs without explicit approval. The native app does not accept untrusted/self-signed certificates and has no insecure bypass.

The implemented backend configuration, **only after review and approval**, is:

```text
PERSONAL_CODEX_DATA=<approved dedicated application data directory>
PERSONAL_CODEX_HOST=<server-tailscale-ip>
PERSONAL_CODEX_PORT=8787
PERSONAL_CODEX_SERVER_NAME=<server>.<tailnet>.ts.net
PERSONAL_CODEX_TOKEN_FILE=<approved owner-only token file>
PERSONAL_CODEX_TLS_CERT=<existing approved trusted hostname certificate>
PERSONAL_CODEX_TLS_KEY=<approved private key file>
PERSONAL_CODEX_RESERVE_GB=200
PERSONAL_CODEX_STORAGE_GB=75
```

Start with `python3 scripts/private_backend.py`. Startup refuses wildcard/public/LAN binds and refuses non-loopback Tailscale binds without authentication and TLS. It does not configure firewalls or prove that an IP belongs to the intended tailnet; verify the actual interface/identity first. Register inference on the backend's loopback interface so private prompts stay on that server. Mac client URL: `https://<server>.<tailnet>.ts.net:8787` with the owner token; no automatic alternate host or cloud fallback exists.

Storage diagnostics cover `PERSONAL_CODEX_DATA` only. The configurable defaults are 75 GB owned-data budget and, on Linux, 200 GB free reserve. Mac development defaults to a 5 GB reserve. Externally managed Ollama weights/caches are not included: measure them separately and reduce the data allocation so total Personal Codex consumption stays within 75 GB. No model download/cleanup endpoint exists. Snapshots refuse reserve/quota exhaustion; general file writes and externally managed models do not yet have an enforced global quota. Do not exceed total budget or reserve without explicit approval.

### Backup and recovery

`GET /api/diagnostics` returns authenticated own-data usage/free-space warnings, CPU/load and retained snapshot count. `POST /api/maintenance/backup` creates a private SQLite snapshot under `data/backups`, verifies integrity, computes a streaming SHA-256, uses no-overwrite publication, checks capacity and enforces a 30-second backup time budget. At seven retained snapshots it refuses another; it never automatically deletes anything. Native settings expose these controls.

Backups include database state only, not repository/worktree files, provider weights or credentials. Keep the same separate approval and storage rules for those assets. Schedule supervision/backups only after server environment discovery and approval; none was installed in this session.

Restore to a new candidate file:

```sh
python3 scripts/restore_database.py <owned-snapshot.sqlite3> <new-owned-restore-candidate.db>
```

The command refuses overwrite and checks SQLite integrity and expected schema. Verify the candidate while the original remains untouched. Replacing a live database is a separate stopped-service maintenance action requiring explicit approval and a preserved rollback copy. Restart recovery marks interrupted operations/messages honestly and never replays partial execution.

### Runtime and update limits

Approved commands still execute with host permissions. Worktrees/allowlists are not an OS sandbox; untrusted test execution next to family backups is not ready. See `docs/THREAT_MODEL.md`. No service, OS-level egress policy, signed update channel, Apple signing identity or notarization was installed/configured. Use reviewed manual bundles and retain an earlier app plus verified database snapshot for rollback.

### Verification

Backend: `PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v` (177 discovered, OK with 4 skips). Default suite: 177, OK with 34 skips. Native: `cd desktop && npm run build && npm test`; `cd src-tauri && cargo test --locked -j 2`. Build: `npm run tauri -- build --bundles app`.

A real local Qwen 14B synthetic coding workflow passed on the Mac. Actual native owner authentication, invalid token rejection and untrusted TLS refusal passed on loopback fixtures. Home/remote Tailscale service operation, server inference and genuine native-to-JARVIS acceptance remain blocked. See `docs/MISSION_1_ACCEPTANCE.md` for the full criterion table.

## Historical deployment notes (retained)

The notes below document earlier milestones. Current instructions above supersede absent-auth/TLS/desktop claims and unconditional model installation suggestions.

## Mac local development

Run `python3 app/server.py` from the repository root. The database will be created at `data/personal_codex.db`, which is ignored by Git.

The service passed an approved loopback smoke test: `/api/health` returned its expected JSON response and the dashboard was served. On the owner's Mac, run `curl http://127.0.0.1:8787/api/health` and open the URL in a browser.

The dashboard supports a release → preview → critical-approved merge → separately critical-approved recovery-branch deletion flow. Resolve conflicts manually in a dedicated workspace; the service only reports them and will not leave the main worktree in a conflicted merge state.

Provider registration is safe to use during local setup because it validates metadata only. It does not probe an Ollama instance, contact a cloud endpoint, or retrieve an environment-variable secret.

Provider invocation now reaches a real adapter per invocation. To probe a local install, start `ollama serve`, pull a model (for example `ollama pull qwen2.5-coder`), register the provider with endpoint `http://127.0.0.1:11434` and that model name, request the invocation approval, approve it, and invoke. The request goes to `/api/chat` and the bounded reply is stored in the ledger. No model is required for the automated tests, which use a stub loopback server.

For an OpenAI-compatible local server (llama.cpp, LM Studio, vLLM), register endpoint `http://127.0.0.1:<port>/v1` and, if the server needs a key, a `secret_ref` naming the environment variable that holds it. The key is read only at call time and is never stored. A cloud endpoint additionally requires `cloud_allowed: true` at registration and a separate `network` approval before each distinct invocation, and its `secret_ref` is mandatory.

The agent workflow adds no new deployment step: create a task, approve its workspace, request an
agent plan approval, approve it, build the plan, approve the proposal digest, then execute. The
dashboard shows the operation list and results. Releasing, previewing, merging, and deleting the
recovery branch keep their existing separate approvals.

If no transport should be available at all, set `server.PROVIDER_TRANSPORT = unavailable_provider_transport`; every invocation then fails closed with a clear message.

## ZimaOS

Do not deploy anything to ZimaOS yet. First collect an authorized, read-only inventory (OS, Docker availability, storage, services, open ports, and CPU/RAM) and choose a non-conflicting port. The eventual worker must be private-network only, authenticated, encrypted, and separately backed up.

## Iterative rounds

`PERSONAL_CODEX_MAX_ROUNDS` sets the per-task round budget (1–10, default 3). `PERSONAL_CODEX_MAX_TASK_SECONDS` (default 1800), `PERSONAL_CODEX_MAX_PROMPT_BYTES`, `PERSONAL_CODEX_MAX_RESPONSE_BYTES`, `PERSONAL_CODEX_MAX_TEST_OUTPUT_BYTES`, `PERSONAL_CODEX_MAX_CONTEXT_BYTES` and `PERSONAL_CODEX_MAX_INVOCATIONS` bound cumulative usage; each is clamped to a safe range and a malformed value falls back to the default. Rounds keep the 8-operations-per-round cap. `PERSONAL_CODEX_STREAM_PROVIDER=1` enables bounded Ollama streaming for round calls; it does not change approval binding. The live diagnostic is run manually (`python3 scripts/live_provider_check.py --model <name>`) and needs no server running. Nothing new is exposed: the round endpoints are part of the same loopback API, so the service still binds `127.0.0.1` only. A cloud provider still needs its per-invocation `network` approval before any round prompt leaves the machine.
