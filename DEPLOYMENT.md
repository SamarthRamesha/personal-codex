# Deployment

## Administration route under investigation

User retained read-only server scope and declined both probes. No separate Docker operator is identified. The supported candidate is owner-operated **ZimaOS dashboard → Apps plus → Install a customized app → Import → Docker Compose**, as documented by IceWhale; no ordinary SSH Docker grant. This is broad owner/admin authority, not proven single-app delegation. Dashboard presence does not prove the session's mutation role. Do not use an undocumented API, web terminal escalation, sudo/group change or management-container workaround.

Before any import/install approval, verify the installed-version importer preserves every required restriction, establish actual image build/load and mapped numeric ownership, and freeze the exact definition/paths. Newer native YAML documentation is not proof for the installed version. No form imported/submitted, image built, directories/secrets/service/Serve/policy changed. Current private ZIMAOS_ADMIN_METHOD_REVIEW.md presents exact method, permissions, sources and gaps for review. Runtime acceptance remains unverified; startup restrictions must not be weakened.


## Mission 1C.1 installation contract

Use the revised Compose profile: `PERSONAL_CODEX_INFERENCE_POLICY=worker-only`, `PERSONAL_CODEX_DENY_CONNECT=1`, data admission24GB within25GB total initial accounting,200GB free reserve and75GB planned maximum. Main private Serve startup now refuses a missing/unsupported no-connect policy; old launch examples require these new flags. Review SECURITY.md for the additive process filter, fixed independent health-check exception and real Linux test gate. Do not build/deploy the historical95e1e0f context as this new restricted release.

Read-only SSH preflight refreshed; no target writes. Existing operator's daemon/Serve/mapping receipt, full policy and revised transient probe approval are pending. Freeze exact mapped identity, protected-root layout, new committed context/image and measured overhead before per-phase directory/credential/build/service/Serve/policy approvals. No sudo/group/API workaround, persistent Mac install, coding enablement or publication. Final local286 tests:281passed/5skipped60.050s, not target enforcement. Current NEXT_SESSION_PROMPT.md/private execution ledger supersede old assumptions below.


## Current read-only review decision

Read-only inspection through the existing unlocked SSH agent now succeeds. Exact target facts are private and outside Git. The original candidate parent fails the strengthened ancestor policy; **`/DATA/PersonalCodex` is the new proposed root, requiring explicit approval**. No directory, permission, mount, service or network change occurred. Earlier path/access descriptions below are historical where superseded.

Read `docs/DEPLOYMENT_REVIEW.md`. Preflight now rejects replaceable/untrusted ancestors before credential reads, and the inventory never treats failed daemon queries as actual capability values. Existing Docker daemon access remains denied to the SSH account; no privilege workaround. Prepare the remaining receipt with an already-authorised operator before filling runtime/Serve fields or executing any installation command.

A deterministic minimal committed API context can now be generated with `scripts/prepare_build_context.py`; no untracked files, diagnostic/runtime data or Docker operation involved. Context reproducibility is tested; actual image build/enforcement remains unverified. The initial profile continues to disable coding.


## Mission 1B update — 2026-11-07

New local security engineering is implemented and tested; no JARVIS deployment or fresh remote command occurred. SSH agent has no loaded identity. An additional public-key-only diagnostic was rejected by automatic approval review because no access change was documented; do not retry pending approval/access change.

- Worker CLI now **requires an existing private `--state-dir`**. Claims are durable before inference and survive crashes; bounded journal exhaustion fails closed. Never delete/reset replay tombstones merely to make capacity available.
- Worker token file is reloaded per request. Owner-only `POST /api/inference/reload-credential` with `{confirm:true}` validates a distinct private replacement, revokes queued/running leases and resets presence; old requests are rechecked after body reads. Token mount is the dedicated read-only two-file credential directory so atomic replacements become visible. No recovery key or unrelated credential may be placed in that mount.
- Initial backend adds `PERSONAL_CODEX_STORAGE_ENFORCE=1` and `PERSONAL_CODEX_DB_MAX_MIB=1024`. It checks free space for each mutation, caches bounded inventory at most one second, closes new writes within a 3 GB safety margin or on incomplete accounting, and caps main DB pages. Auth, read, cancellation/heartbeat and credential revocation remain available for recovery. This is **not an overall filesystem quota**.
- `deploy/base-image.lock.json` pins official Python Linux/amd64 manifest/config hashes; compressed layers total 44,201,486 bytes. Only small public metadata fetched and verified, no layers/pull/build/signature/vulnerability scan. Both Dockerfiles require the pinned reference at reviewed build time. Source plus base digest enables repeatable inputs; byte-for-byte image reproducibility remains unverified. Explicit download/build approval still required.
- `scripts/deployment_preflight.py --docker-readonly` inspects only the local daemon and reviewed cached image: versions/resource capability flags/built-in seccomp/image ID/platform/size/implicit volumes/build triggers. It cannot certify actual container enforcement before startup. No sudo, pull, build, exec or service change.
- Operator-only isolated executor prototype has no host mounts or networking; see `docs/ISOLATION.md`. It refuses missing Linux controls, never enables backend coding, and has no actual Docker runtime proof.
- Encrypted offline multi-component recovery and new-root restore are tested; see `docs/RECOVERY.md`. Full envelope limited to 64 MiB; exceeding it needs a separately reviewed streaming backup solution. No credentials/private keys collected and no automatic scheduling/retention.
- `scripts/check_deployment.py` is a **read-only** HTTPS/auth/readiness/worker-scope/storage check, never a real coding/stream/restart/ACL acceptance substitute. It rejects self-signed TLS before credentials; run only after approved private installation with exact private origin/token files/model.

The optional executor/runtime image and its staging/rootless data must be accounted separately within the same 75 GB total allocation; do not assume two 512 MiB image limits fit the existing 1 GB overhead allowance. Measure actual image/source/log/runtime size, reserve headroom and obtain a revised allocation plan before adding it. Existing rootful Docker/Tailscale is never reconfigured to enable jobs. Actual kernel/quota/LSM/cgroups/policy facts remain unavailable. Initial safe API profile stays chat/planning/review only.


## Current decision — 2026-11-07

Preparation is implemented; JARVIS is not deployed. The user supplied the server inventory and reports interactive SSH/MagicDNS success. This unattended session's strict dedicated-key SSH attempt failed authentication; no remote command ran. Exact device/account/path details are in PRIVATE_DEPLOYMENT_NOTES.md outside Git. Family data and existing services remain off-limits.

The initial reviewed profile is **chat/planning/review only**. Repository commands, Git subprocesses, worktrees, code proposals and patch application are disabled. High-level task planning and chat remain available. Worktrees and allowlists do not contain malicious code; coding execution on JARVIS needs a separate approved OS containment and egress design. Mission 1 remains partial until remote acceptance is verified.

## Prepared artifacts

- `deploy/Dockerfile`: stdlib backend/web only; requires an explicitly reviewed official Python image digest. No package installation or Git. Build context allowlist in `.dockerignore` excludes diagnostics, working data, keys and Git metadata.
- `deploy/compose.review.json`: nonroot UID/GID, read-only root filesystem, all capabilities dropped, no-new-privileges, 1 CPU, 512 MiB memory with no additional swap allocation, 128 PIDs, 16 MiB tmpfs, bounded Docker logs (2 MiB × 3), liveness probe, restart policy and 15-second grace period. No Docker socket, privileged mode or published ports. Existing Tailscale container is untouched.
- `deploy/review.env.example`: five nonsecret literal settings. Copy outside Git, replace all review placeholders. `PC_IMAGE` must be a reviewed local image ID; pull policy is never.
- `scripts/deployment_preflight.py`: read-only inspection of the five settings and exact dedicated paths; no mkdir, shell expansion, Docker mutation or shared-storage scan (optional scoped daemon/image queries only). Requires pre-existing private directories, reviewed numeric ownership, distinct 0600 tokens and at least 205 GB free. A passing preflight still reports overall readiness false until external checks pass.
- `deploy/local.personalcodex.mac-worker.plist.example`: prepared outbound-only LaunchAgent, not installed. Replace executable/repository/private paths and exact backend origin. Worker log is private and rotates at 256 KiB × 3; no prompt, URL, token or exception details in log messages.

Docker is unavailable in this Mac environment. JSON/property/preflight tests pass; no Docker build, Compose parse against the actual server version, container startup or server resource enforcement has been tested. Do not describe static template checks as container integration tests.

## Storage and isolation proposal

Use only an approved dedicated `PersonalCodex` root under the server's application-data parent:

```text
PersonalCodex/                 # private 0700, approved nonroot UID/GID
  data/                       # mounted /var/lib/personal-codex
    personal_codex.db          # initialized by backend only after approved startup
    projects/                 # explicit allowed project root, no family mounts
    workspaces/               # execution disabled in initial profile
    backups/                  # maximum seven snapshots, no automatic deletion
  secrets/                    # separate 0700 directory
    owner-token               # unique 0600, never included in Git/build/image
    worker-token              # distinct scoped 0600, securely copied to Mac after approval
```

The service data budget is 74 decimal GB, reserving 1 GB of the 75 GB total allocation for image/source/log overhead. Readiness and backups enforce measured storage checks; these are not a filesystem quota and do not prevent every database growth event. A hard quota/monitoring and actual image/source/log accounting still require review before unattended production use. Preserve at least 200 decimal GB free. No model downloads or inference installation on JARVIS.

Host networking keeps the Python listener truly on host `127.0.0.1:8787` so the existing host-network Tailscale Serve can reach it. It also shares the host network namespace and is **not network containment**. No OS egress sandbox is supplied by this template. Keep execution disabled; do not add family mounts or broad bind paths. Approved installation must verify the actual Docker/Compose version honors every constraint.

## Approval-gated deployment sequence (not executed)

Every step below that writes a server, installs/pulls an image, creates a service, persists a Mac worker, or changes Serve/ACL requires approval. Do not treat this document or a successful preflight as authorization.

1. Restore unattended read-only SSH using the user's existing access method; no password/key/agent changes or privilege workaround. Inspect only current free space, dedicated-path existence, numeric identity, Docker permission/version and named existing Tailscale/Serve settings. Do not scan personal data. Verify port 8787 is free.
2. Review numeric service UID/GID, exact private origin/root, image digest/size/provenance, filesystem quota, approved project roots and current full tailnet policy. Reserve 200 GB; cap total app allocation at 75 GB. Review host-network risk and execution-disabled acceptance.
3. After approval, create only the exact private layout and release staging path. Generate each token with the existing no-overwrite helper as the approved service identity, never on a command line or in logs. Transfer only worker credential to an approved private Mac file; native owner token remains in process memory while connected.
4. After download/build approval, build the source allowlist for Linux x86_64 from the pinned Python image. Record `docker image inspect` ID/size/architecture, do not use a mutable tag at startup. No push or third-party source upload is needed. Validate locally staged settings/layout:

```sh
python3 scripts/deployment_preflight.py "$PC_REVIEW_ENV"
docker compose --env-file "$PC_REVIEW_ENV" -f deploy/compose.review.json config --quiet
# MUTATION — execute only after explicit installation approval:
docker compose --env-file "$PC_REVIEW_ENV" -f deploy/compose.review.json up -d --pull never --no-build
```

5. Verify liveness over loopback, unauthenticated owner routes return 401, authenticated readiness and execution rejection. Inspect actual listener bind/resource limits/log limits/mounts; no external backend port. Run a real synthetic snapshot/restore-to-new-path check, preserving original state.
6. Snapshot current Serve configuration privately and confirm HTTPS 443 has no existing handler to overwrite. With approval only, use the **verified existing** container name:

```sh
docker exec "$PC_TAILSCALE_CONTAINER" tailscale serve status --json
# MUTATION — only after Serve approval and a conflict-free configuration review:
docker exec "$PC_TAILSCALE_CONTAINER" tailscale serve --bg --https=443 http://127.0.0.1:8787
```

Do not reset/recreate Tailscale, touch its volumes/capabilities, run Funnel or bypass certificate validation. Confirm actual v1.98.3 CLI syntax from its help. If a handler exists, prepare a revised scoped plan instead of overwriting it. HTTPS termination follows [Tailscale Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve).

7. Review the full ACL/grants policy and family-app dependencies before changing anything. A narrow grant does not restrict an existing allow-all rule: grants combine permissions. Prepare Mac → backend TCP 443 and SSH TCP 22, deny direct TCP 8787, and no backend → Mac Ollama listener. The outbound worker requires no inbound Mac service. See [grants syntax](https://tailscale.com/docs/reference/syntax/grants). `deploy/tailnet.fragment.example.json` is a synthetic fragment with tests, never a replacement policy; exact private fragment is outside Git. Preserve existing family access and emergency administration, validate policy tests before saving with approval.
8. After approval, run the Mac worker interactively first using its explicit private backend URL, distinct token file and installed allowlist. Verify real model status/chat/stream/stop/retry across private verified HTTPS. Then approve any persistent LaunchAgent installation separately. Keep Ollama bound to loopback, no listener/networking change or model download.
9. Native acceptance: verified HTTPS, owner auth, model MAC location, persistent chat, cancellation/retry/restart, project/review state, execution refusal, backup/recovery. Check unauthorised tailnet device rejection after ACL change. Only then assess the limited initial deployment as passed; full coding mission still needs OS containment.

Long bind syntax with `create_host_path: false` avoids implicit host directory creation, as described in [Docker Compose services](https://docs.docker.com/reference/compose-file/services/). This remains a proposal until exercised on the target.

## Backup, recovery and rollback

`POST /api/maintenance/backup` creates one verified SQLite snapshot at a time, with SHA-256, integrity check, capacity/reserve checks and seven-snapshot retention refusal. Incomplete own-data measurements fail closed. This captures SQLite state only: it does not back up Git repositories/worktrees, model files, secrets or service configuration. No automatic backups or cleanup are scheduled. A production backup schedule and retained storage destinations need approval.

Copy/restore into an explicitly **new** path with `python3 scripts/restore_database.py SNAPSHOT NEW_DATABASE`; existing destinations are refused. Verify integrity and expected records in a disposable instance before switching a service. Stop only the dedicated backend, retain the previous image/source/database, and review schema compatibility before any approved switch. Startup interrupts in-flight work; it never replays patches, tests or inference jobs. An approved rollback must reconcile worktrees/operation ledger with restored state before enabling execution. Never overwrite a live DB or delete recovery data automatically.

For a newly created, otherwise unused 443 Serve handler, reviewed rollback removes only that handler (`tailscale serve --https=443 off`) via the verified existing container; never `serve reset`. If other handlers/configuration exist, restore the reviewed scoped change instead. Stop the dedicated Compose project only after approval; do not use `down -v`, prune, remove images or delete data. Worker rollback unloads only its separately approved LaunchAgent; no Ollama/Tailscale changes.

## Local development

`python3 -m app.server` defaults to unauthenticated loopback development with repository execution available under approval gates. For real local data use `PERSONAL_CODEX_TOKEN_FILE` and the no-overwrite `scripts/private_backend.py --create-token PATH` helper. Browser root now has cookie sign-in/sign-out; native uses the in-memory bearer bridge. Never put tokens in URLs or browser storage.

Development mode is for trusted local fixtures. The private Serve configuration requires disabled execution, explicit project roots and a distinct worker credential if enabled. A packaged native app connects to an existing backend and does not install or launch a persistent backend itself.
