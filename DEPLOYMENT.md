# Private home-server deployment

**Status: prepared and locally tested, not deployed on JARVIS.** No command in this guide authorizes a server change. Use the owner's current private approval package to freeze exact operations; it is deliberately excluded from this public repository.

## Intended arrangement

The Mac runs the native client, local model and outbound inference worker. JARVIS hosts persistent conversations, projects, task state and the authenticated API. Tailscale Serve supplies private HTTPS to a loopback-only backend. Ollama is never exposed as a public or tailnet listener.

The initial server profile is worker-only and repository execution stays disabled. Mac opening actions are a separate native-local capability: no server HTTP route can invoke them. General remote Mac automation would require a separately reviewed capability/broker design.

## What has been tested

Exact API source `282b90d759c2cf76e3306fe87ee6a1f74f7922f2` passed 17 actual container checks in a disposable Debian/Linux machine. This is historical container evidence. Build and review the image for the exact current release before any installation. The checks cover authenticated readiness, owner/worker separation, execution-disabled/worker-only behavior, additive no-connect filtering, actual runtime resource/mount controls, document index/removal, the proposal guard and restart persistence. See [container verification](docs/CONTAINER_VERIFICATION.md).

These results do not prove JARVIS's Docker identity mapping, importer behavior, service configuration, quota, TLS, access policy or coding executor. The disposable machine is stopped and its snapshot is preserved.

The owner reported JARVIS online on 27 November. No authorized target connection was available in the release workspace. The earlier connectivity check observed private DNS and a reachable dashboard port, with private HTTPS 443 and proposed API 8787 refusing connections. Target readiness needs a fresh authorized check.

## Required facts before installation approval

| Area | Required evidence |
|---|---|
| Existing administration | The chosen supported owner method, exact permissions and installed ZimaOS version |
| Custom App importer | Every required field retained; no unapproved pulls or implicit directory creation |
| Image | Exact current context/source, supported load/build method, actual resulting image identity/architecture/size and staging accounting |
| Dedicated storage | Protected parent, exclusive new path, exact numeric host/container mapping and supported ownership method |
| Capacity | Fresh exact free bytes, measured image/data/log/staging/recovery footprint and required reserve |
| Existing services | Actual Tailscale container, node/Services Serve mappings, port/certificate status and family endpoint conflicts |
| Access | Complete current policy, device/tag/share/route/exit-node/service relationships, emergency administration and vendor validation |
| Recovery | Scale-appropriate restore acceptance, approved key custody and off-device destination/schedule |

An existing owner dashboard is broad authority, not verified per-application delegation. Do not add the ordinary SSH account to Docker, use sudo as a workaround, install a privileged helper app, reset credentials or use an undocumented privileged API. Two earlier target filter probes were declined; they must not run or be requested again. Never assume unverified family access mechanisms are absent.

## Reviewed runtime contract

`deploy/compose.review.json` is the complete preparation template. Do not recreate it from a subset of GUI fields.

- Reviewed local image identity with pull policy `never`; no host package installation or registry publication required by this design.
- Explicit numeric nonroot user/group with verified host mapping.
- Read-only root, all capabilities dropped, no-new-privileges, 1 CPU, 512 MiB RAM, 512 MiB memory-plus-swap ceiling and 128 PIDs.
- Bounded 16 MiB noexec/nosuid/nodev temporary filesystem, file-descriptor limits and rotating Docker logs.
- Only a dedicated data bind and a separate read-only token bind; missing source paths must not be implicitly created.
- Host networking solely to retain a real host loopback listener at 127.0.0.1:8787 for the existing private proxy. Host networking is not network isolation.
- `PERSONAL_CODEX_EXECUTION_MODE=disabled`, `PERSONAL_CODEX_INFERENCE_POLICY=worker-only`, `PERSONAL_CODEX_DENY_CONNECT=1`, gateway disabled and storage enforcement enabled.
- Exact reviewed private HTTPS origin, owner/worker authentication, healthcheck, unless-stopped restart and graceful stop.

The API's no-connect filter is additive process-local defense, not a complete sandbox. Docker healthchecks/exec processes do not automatically inherit it. Production coding needs a separate actually accepted OS executor and narrow broker; the API never gains Docker authority.

## Storage and recovery

The strict initial plan is **25 decimal GB total**, with **24 GB API data admission**, while preserving **200 GB free**. The overall project ceiling remains **75 GB**; it does not authorize a 75 GB initial allocation. Count attributed image/layer growth, build staging, source/releases, logs, snapshots, credentials and recovery copies. Do not treat rounded dashboard numbers or old free-space observations as current admission proof.

Admission checks and the SQLite main-page cap are not a whole-filesystem quota. No hard quota is verified on JARVIS. Incomplete inventory or breached margins must stop the proposed operation; never prune shared images, delete backups or change shared-parent permissions to make room.

The proposed new private tree has dedicated `data/`, `secrets/`, `release/` and `recovery/` children. Its exact parent, numeric ownership and creation method must be approved. Existing paths stop exclusive creation; retain partial work for review rather than broad cleanup. Owner and worker tokens are distinct private files, never shell arguments, logs, images or committed source.

Encrypted recovery currently supports a **64 MiB plaintext envelope**. That is not 24 GB production backup capacity. Larger recovery, key escrow/custody, scheduling and off-device retention are separate unfinished gates. [Recovery contract](docs/RECOVERY.md).

## Safe approval sequence

1. Finish read-only inventory and installed-version preservation checks. Prepare exact image/directory/container actions with fixed identities, capacity accounting, rollback and expected results.
2. Obtain approval for those exact new resources. Create only the dedicated tree and securely generated credentials; verify ownership and image/context identity before startup.
3. Start only the new Personal Codex service. Verify effective nonroot/capability/seccomp/resource/mount/listener/auth/readiness/restart behavior on the target. On failure, stop the new app and retain its data.
4. Separately review/approve a conflict-free private Serve change and complete exact access-policy diff. Preserve every required family and emergency route; never reset Serve or treat adding a narrow grant as removal of an existing broad one.
5. Install a persistent outbound Mac worker only after its exact service/credential approval. Test actual HTTPS, installed-model discovery, streaming, stop/retry, reconnect, Mac sleep, server restart and denied clients in both address families.
6. Complete production-scale recovery/storage checks. Keep repository execution disabled until separate adversarial containment/broker acceptance and approval.

`scripts/check_deployment.py` performs read-only authenticated acceptance after a real HTTPS backend and credential files exist. It does not install a service or prove full remote acceptance. Current missing credentials must not be bypassed or invented.

## Rollback principles

Before any policy change, retain the complete actual baseline/hash and existing recovery administration session. Validate the proposed diff using vendor tests; on failed access checks, restore that captured baseline through existing authority.

App rollback addresses only the exact newly named Personal Codex container and any separately approved new proxy handler. Stop/remove it with data retained. Do not delete private directories/credentials/backups, prune shared images, reset Serve, recursively alter permissions or change family applications. A changed baseline requires fresh review.

## Prepared tools

- `scripts/prepare_build_context.py`: deterministic committed-source allowlist; excludes untracked/runtime/private data.
- `scripts/deployment_preflight.py`: read-only path/identity/capacity/credential metadata checks; never creates missing resources.
- `scripts/check_deployment.py`: bounded strict HTTPS/auth checks, no inference or mutation.
- `deploy/local.personalcodex.mac-worker.plist.example`: outbound worker service template, not installed.
- `deploy/tailnet.fragment.example.json`: illustrative fragment only; it is not a complete deployable policy or a narrowing of existing allow-all access.

Do not put private target addresses, live policy, keys, credentials or operator receipts in this public repository.
