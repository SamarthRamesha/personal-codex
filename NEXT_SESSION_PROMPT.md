# Personal Codex: current implementation handoff

## Mission 1C.1 execution checkpoint

Read-only SSH preflight succeeded again after the user unlocked the existing agent. Exact target/account/device/model receipts stay outside Git. No persistent directory, secret, image, service, Docker/network/Tailscale or permission change has been approved/performed. Current account still lacks Docker socket access. User asks an existing authorised Docker operator to supply the scoped checklist output; no operator login/session or receipt has yet been supplied. Do not use sudo, broaden groups or use an indirect privileged workaround.

The stricter deployment directive requires lower initial storage and outbound restrictions. Compose now sets24 decimal GB data admission within the25GB initial total target (including at most1GB reviewed external overhead), retaining200GB free and75GB maximum planned allocation. This is not a hard quota. Existing3GB admission headroom and1GiB main DB cap remain. Actual Docker layers/build/log overhead needs operator measurement.

`app/network_policy.py` enforces worker-only providers before registration, stored-model discovery, chat/round/invocation transport and injected chat writes. Private Serve startup requires worker-only plus the additive Linux x86_64 no-connect guard before the server/threads start. It refuses inherited sockets; applies no-new-privileges and thread-synchronised seccomp; denies connect, non-TCP socket creation, socketpair, sendmsg/sendmmsg, TCP Fast Open/destination-bearing sendto, io_uring and selected cross-process FD/memory routes. Packet-free invalid-FD startup tests supplement connect/datagram tests. Normal accepted TCP responses remain supported by design. Unsupported/failed guard stops startup. No host firewall, daemon configuration or existing service changes. Fixed Docker health checks are independent processes outside this application filter; this exception must remain fixed/trusted/read-only. This filter is not a coding sandbox, ingress bind filter or complete kernel-escape defence.

Fresh final HTTP suite: **286 discovered,281passed,0failures/errors,5skipped,60.050s**. Skips:3 disabled optional gateway,1 Mac-inapplicable proc check,1 explicitly opt-in real Linux filter test. Portable policy vectors do not prove kernel enforcement. Earlier285 run280pass/5skip60.775s predates the Fast Open correction; final286 supersedes it. A fixture child-string escaping error was corrected and the synthetic loopback fixture was verified locally before requesting target approval. No real model/native build rerun for these changes.

A revised stdin-only nonroot Linux probe is prepared outside Git, SHA256 `6f42acea8f241549d8c0b31119614b33314f172c83b8c61d4df624692c2c5fb7`; the earlier unexecuted draft is superseded. User approval is pending because it restricts its own process and opens one temporary synthetic loopback socket. Neither draft has executed on target. Approval is not permission for installation. Actual daemon/Serve/image/isolation/HTTPS/remote worker/native/recovery acceptance remains unverified. The current tailnet admin page requires sign-in; no policy was read/changed. Mac client peer metadata is not full policy or a family-access specification.

Continue by receiving the revised probe decision, existing operator's read-only daemon/Serve/mapping receipt, and current full policy/sign-in. Freeze exact protected-root identity/layout, reviewed new source/context,25GB accounting and per-phase commands before asking for directory/secret/build/service/Serve/policy/credential transfer approvals. Never deploy the prior95e1e0f context as the new restricted release. Keep execution disabled; preserve all local history and the untouched untracked diagnostic. No push/publication or persistent Mac worker installation. Mission1 remains partial.


## Read-only infrastructure review completed — 2026-11-07

The user unlocked the existing SSH identity. Normal authorised metadata inspection succeeded through that agent, with strict existing host verification and no forwarding/private-key read or SSH/agent change. SSH is resolved; old empty-agent/diagnostic/review-block descriptions below are historical. Do not repeat the consumed public-identity diagnostic or ask for another unlock while access remains usable.

Exact target/account/kernel/storage/DNS/TLS receipts remain outside Git. Docker daemon/Serve inspection is blocked by current socket permissions; do not use sudo, group/ACL changes or an alternative privileged API. Obtain an already-authorised operator's scoped read-only receipt. Kernel prerequisites were observed, not container enforcement. Private DNS resolves; private TLS connection was refused, so no certificate/Serve readiness is claimed. Full current tailnet policy and family/admin relationships remain missing.

The old application parent is replaceable by other users. New proposed root `/DATA/PersonalCodex` requires approval; nothing was created or changed. Preflight now checks every ancestor's ownership/writability/sticky policy before credentials. Numeric identity remains a candidate until actual userns mapping is known. AppArmor prototype now accepts only enforcing mode. Deterministic minimal build context comes only from reviewed committed Git objects, with no untracked files or runtime/diagnostic content. Context reproducibility is not image reproducibility.

Final relevant regression: **276 discovered, 272 passed, 0 failures/errors, 4 skipped, 59.544s**, HTTP profile. Three optional disabled gateway tests and one Linux/proc observation skip on macOS. Eight new regressions cover ancestor boundaries, deterministic committed-only context and AppArmor enforcing labels. No real Linux/Docker enforcement passed. Historical Qwen worker19/19, recovery6/6, frontend7/Rust3 remain historical and were not repeated for these changes. No new native binary or remote end-to-end proof.

Private `JARVIS_FINAL_APPROVAL.md`, `JARVIS_VERIFIED_READONLY_FACTS.json`, operator checklist and final artifact manifest supersede previous private queue/access/path assumptions. Final reviewed source commit/context/archive hashes are in that manifest; use git log for current tip. No server installation, directory, permission, Docker/network/Tailscale change, backup traversal, persistent Mac worker or publication occurred. Coding stays disabled. Mission1 remains partial; final installation readiness depends on the operator/policy receipts, explicit phased approvals, real image/runtime/HTTPS/remote acceptance and the documented recovery/storage limits.


## Latest SSH continuation — approved diagnostic completed

The user explicitly approved exactly one public-key-only handshake after the earlier automatic-review rejection. It completed: network connection established, existing known host key matched, and server recognised the supplied public identity. Agent/password/interactive signing were deliberately disabled; authentication did not complete (expected exit255), and no remote command ran. No private key read, configuration/agent change or installation. Private receipt outside Git updated.

That one-shot approval is consumed. Do not repeat the diagnostic. The earlier review block for that exact action is superseded by this explicit approval/result; ordinary remote infrastructure facts remain unverified. Next requires the user to unlock the existing key in their own existing local agent, without sharing the passphrase/key or enabling forwarding/persistent key storage. After an actual access change, verify agent identity and resume already-authorised read-only inspection. No deployment/service/Serve/ACL permission is implied. Earlier checkpoint descriptions of the diagnostic as pending are historical.

## Mission 1B authoritative implementation checkpoint — 2026-11-07

The Mission 1B user directive supersedes the earlier AFK milestones below. Continue existing branch and preserve all history. No deployment, GitHub publication, server write, persistent Mac service, externally reachable listener or model download is approved. Only disposable authorised loopback HTTP/TLS tests were used. Do not read/stage/delete/publish the pre-existing untracked diagnostic. Exact targets/access/approval queue remain outside Git in current outputs. No new user changes were found at entry; starting source was 6c0c101. Mission1B implementation saved locally as `440c78afd252551fbb5a8347ccd36f5ce7461449`; a documentation receipt follows. Run git log for current tip.

### Current implementation

- `app/worker_state.py`: private durable SQLite claim before any model invocation, no prompt/token content, 10000 retained claims then fail closed. No automatic reset/tombstone archival. Production CLI requires pre-existing private `--state-dir`.
- Worker protocol now strictly validates poll/heartbeat/append/UUID/JSON fields, duplicate keys, byte/framing/sequence/empty-chunk bounds and completed/streamed consistency. Monotonic consumer timeout and future-presence handling survive wall-clock rollback.
- Owner-only `/api/inference/reload-credential` with exact boolean confirmation reads only configured replacement file; distinct private credential required, unchanged token is no-op. Rotation interrupts active jobs, clears leases/presence, rechecks worker authority after slow request bodies. Worker re-reads private token every request. Credential directory mount allows atomic inode replacement; contains only two token files, no recovery key.
- `app/secure_files.py`: descriptor-relative bounded snapshots, no links/special files/aliases/protected diagnostic/control paths, change detection and known broad/family/other-app scope refusal before inventory. These improvements do not replace every legacy direct file tool's path-race boundary.
- `app/recovery.py` / operator CLI: offline locked encrypted DB + dedicated project/workspace/Git files + release zip + five nonsecret settings. Optional existing cryptography49.0.0, backend remains stdlib. Complete plaintext envelope **64MiB max**; larger-data/75GB disaster recovery not implemented. No plaintext staging archive or credential/key collection. New-root restore relocates DB paths, revokes pending/approved approvals, interrupts active jobs/messages/operations, marks workspaces recovery-review and writes startup lock before payload/completion receipt last. Git pointers require isolated review/repair; credentials regenerated.
- Storage: mandatory admission in private Serve mode; bounded2s/100k-entry inventory cached<=1s, free space every new mutation,3GB margin, main SQLite page cap<=1GiB. Auth/read/stop/cancel/heartbeat/revocation remain available. No total filesystem quota; overhead/images/runtime/releases/logs still need actual accounting. Existing DB hardlink aliases refused.
- Isolated executor **operator-only prototype**, no backend integration/new execution mode/Docker authority. Bounded8MiB/2000-file approved stdin source, no Git/secrets/host mounts/network. Fixed reviewed image/argv, required trusted Linux userns/seccomp/AppArmor/capability/cgroup/tmpfs probe before tests. Host supervisor independently bounds output/time and claims before Docker; ambiguous jobs never replay. No actual Docker/Linux enforcement test passed here; server coding remains disabled.
- Public official Python OCI lock: Linux/amd64 digest,44,201,486 compressed layer bytes. Metadata only fetched/verified; no layers/pull/build/install/signature/CVE/reproducibility proof. Default backend and separate executor Dockerfiles remain review artifacts.
- Scoped read-only isolation inventory, cached-image/daemon preflight and HTTPS/auth/storage checker implemented. Checker onlyGET, no inference/task/service mutation; actual local self-signed certificate rejected before credentials sent. Complete remote acceptance remains separate.

### Exact current verification

- Python HTTP profile: **268 discovered,264 passed,0 failed/errors,4 skipped,59.754s**.
- Default profile with authorised local sockets: **268 discovered,213 passed,0 failed/errors,55 skipped,22.517s**.
- Full skips:3 optional disabled gateway dependency,1 Linux/proc observation inapplicable on Mac. Default skips51 additional opt-in HTTP tests. Recovery cryptography available; recovery tests executed, not skipped. No test removed/weakened.
- Frontend TypeScript/Vite production build passed1.02s;7 Vitest passed;3 Rust passed. Desktop source unchanged; no new native bundle/UI proof claimed. Prior optimized app/native UI proof retained historically.
- Real installed Qwen worker workflow **19/19 passed,46418ms**. Actual patch/test/completion/restart plus durable Mac journal restart/refused completed-ID replay. Synthetic only, no private repo/model download; test backend/worker exited.
- Encrypted synthetic recovery drill **6/6**,9ms checkpoint/10ms restore for a tiny warm local fixture: Git/history/source/DB/RPO checks and explicit preservation query. Not JARVIS RTO. Unit recovery10, isolation/supervisor13, worker inference20 + hardening11, storage5, metadata4 and acceptance3 are subsets of full suite.
- Python compile, JS syntax, shell syntax, JSON/plist/static constraints and Git diff whitespace passed. Metadata/CDN resolution originally failed closed on307; added exact Docker CDN allowlist with no auth-header forwarding, digest verification succeeded. Initial recovery tests had8 fixture setup errors (missing ledger round_id); fixed fixture then10 passed. Preserve failure receipts separately.

### SSH and actual JARVIS evidence

Only local SSH metadata/agent inspection occurred: dedicated key exists owner0600, public file present, config absent, known_hosts0600, agent reachable but **no identities loaded**. Existing passphrase-protected identity cannot sign in BatchMode without an interactive unlock. No private key read, passphrase request, keychain/passwordless storage, agent/config modification or new identity.

Automatic approval review **rejected** the proposed additional public-key-only diagnostic because no access change was documented since earlier failures. Command never executed; do not bypass via another tool/remote shell or retry unchanged. A pending asynchronous question requests that exact diagnostic approval. A real agent unlock/access change permits renewed authorised read-only inspection after confirming it. No remote command, fresh kernel/runtime/storage/Serve/certificate/policy fact or target acceptance obtained in Mission1B. User-provided historical inventory remains historical.

### Next action and deployment gates

Read `docs/THREAT_MODEL.md`, `docs/ISOLATION.md`, `docs/RECOVERY.md`, `DEPLOYMENT.md`, `docs/API.md` and the private queue. First obtain a real access change/explicit blocked-probe decision, then inspect only authorised metadata. Do not guess identity, cached image ID, policy relationships or free space.

Actual Linux cgroup/LSM/userns/runtime proof, bounded image build/size/provenance, full family-aware ACL/current device policy, HTTPS certificate, source-device rejection, remote model/native stream/stop/retry/restart, target recovery and existing service health remain unverified. The complete policy proposal cannot be finalised without its current policy/device/family/admin facts.

Approve exact dedicated layout/ownership, bounded image download/build, API service, Serve/full ACL changes, persistent Mac worker/state/logs and optional recovery dependencies/key escrow/schedule separately. Never change existing Docker/Tailscale to make the prototype work, never enable production coding without actual containment + separate narrow broker integration, never reset replay journals, never delete backups automatically. Before exceeding64MiB recovery scope, approve/test vetted streaming encrypted backup tooling. Overall75GB/200GB reserve and executor/rootless overhead need measured review; main DB cap is not whole-volume quota.

Mission1 remains **PARTIAL**. Local engineering/review artifacts are ready; production/security certification is not. Read-only access is already authorised but currently unavailable/review-blocked; no need to ask routine architectural questions. Safe future work depends on these facts for the correct runtime/integration choice. No automatic GitHub push or deployment.

Deliverables under current chat outputs: MISSION_1B_REPORT.md, MISSION_1B_ARTIFACTS.json, current source archive, AFK_APPROVAL_QUEUE.md, PRIVATE_DEPLOYMENT_NOTES.md, MISSION_1B_SSH_LOCAL_INSPECTION.json, MISSION_1B_RECOVERY_VERIFIED.json, mission-1b-live-worker/evidence.json and mission-1b-evidence logs. Old outputs/AFK artifacts retained. See final local report/Git log for exact new commit tip; earlier checkpoint narrative below is historical.

Current as of 2026-11-07, Asia/Kolkata. Continue the existing checkout; do not recreate it. Latest AFK autonomy instructions permit ordinary local code, tests, synthetic fixtures, native builds, documentation and local commits. Queue infrastructure approvals and continue independent work. No automatic deployment.

## Repository and preservation

- Repository: `https://github.com/SamarthRamesha/personal-codex`.
- Checkout: `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`.
- Branch: `personal-codex/stabilization`; historical published tip `4a3ea1d91e70e392faf342ea03b335d7f207169d`.
- AFK core milestone `9109eb1`: durable outbound worker, private proxy/runtime and native contract fixes. Local preparation implementation commit `31f5f1d` adds the final browser, maintenance, profile/path enforcement and deployment artifacts. A documentation receipt follows; use `git log -3` for its exact tip. No AFK changes pushed.
- Preserve all local work. Never reset, clean, rebase, force-push, delete recovery data or overwrite unexpected edits.
- Pre-existing untracked `personal-codex-diagnostic.txt` is excluded: never read, stage, delete or publish it. Use explicit staging paths, never `git add .`.
- Private deployment targets, SSH identity metadata and approval queue are outside Git under current chat outputs. Do not copy them into public docs/source archives.

## Current result

Mission 1 is **PARTIAL**. The single-owner native/local backend coding slice works, including real local-model patch/tests/completion. The intended production architecture is Mac native UI + loopback Ollama inference, JARVIS API/persistence/orchestration and private existing Tailscale Serve HTTPS. No JARVIS app directory, container, service, Serve/ACL/firewall/SSH change, model download or Mac inbound listener has been created.

User reports interactive dedicated-key SSH/MagicDNS success and supplied server inventory. This unattended session's strict dedicated-key BatchMode SSH failed authentication (`publickey,password`); no remote command ran. Do not reinterpret this as a fresh server inspection. Do not retry unchanged credentials, request secrets, change agents/keys/SSH or use sudo workarounds. Resume read-only inspection only when access changes.

## Implemented architecture

- `app/server.py`: SQLite schema/additive migration/recovery, exact approvals and operation ledger, chats/projects/tasks/rounds/context/memory/files/diffs/tests, auth/readiness/diagnostics/snapshot APIs. Lazy Store import avoids incidental DB recovery; process startup locks data root first.
- `app/security.py`: owner-only regular token files, bearer/hashed expiring cookie sessions, login throttling, Host/Origin/Sec-Fetch checks, duplicate header rejection. Explicit exact private Serve origin trusts forwarded Host/HTTPS only from HTTP loopback; identity does not authorize requests. Direct authenticated private TLS listener retained.
- `app/runtime.py`: private single-instance flock, 32-client cap, 10-second client sockets/deferred TLS handshake and graceful SIGINT/SIGTERM shutdown/drain. Interrupted operations/generations are never automatically replayed.
- `app/inference.py`: durable outbound-worker jobs; max four active, one running, 15-second leases, 30-second worker presence, 100,000-byte prompts, 200,000-byte responses, ordered/idempotent chunks, bounded deadlines, cancellation, startup interruption, 10,000-row retained-metadata cap. No automatic audit deletion; exhausted retention needs reviewed archival. Ephemeral job payload clears after consumption/recovery; normal chat/invocation history persists. Not secure erasure of SQLite pages/backups.
- `app/mac_worker.py` / `scripts/mac_worker.py`: outbound authenticated private HTTPS polling; fixed loopback Ollama, installed explicit allowlist, closed job schema/digests, no filesystem/shell/download/arbitrary proxy capability. Distinct worker token has no owner authority. Control loss cancels inference. Rotating 0600 logs, optional existing 0700 directory, generic messages only. No inference retry/cloud fallback. JSON escaping accounted under a bounded control-response cap and total deadline.
- `app/providers.py`: local Ollama/OpenAI-compatible adapters/discovery, bounded real streaming; cancellation/total-deadline guard shuts down detached HTTP/1.0 sockets too. Native provider tool-calling protocol is not implemented; strict model-proposed JSON tools are the coding interface. Optional Respan gateway remains disabled by default and unused.
- `app/conversations.py`: ordered persisted chunks/resume cursor, bounded recent context, one generation per chat/two total, retry/stop/search/history, worker transport seam and shutdown drain. No cloud chat/self-created consent.
- `app/context.py` / `app/tools.py`: bounded ignore/secret/symlink-pruned context/search, hash-bound exact patches and approved tests/diffs. Worktrees/command allowlists are not an OS sandbox.
- `app/maintenance.py`: bounded own-data inventory; errors mark measurement incomplete; private verified SQLite snapshots, one at a time, seven retained then refusal, SHA/integrity/time/capacity checks and restore-to-new-file only. Snapshots do not back up repositories/worktrees/secrets/models/configuration.
- Private Serve profile **requires execution disabled and explicit project roots**. Code proposal generation, patch application, Git, worktrees and interpreter routes are blocked before approvals/tools. Persisted project paths are rechecked on file/search/summary access; persisted workspace reads must remain in the dedicated data workspace root and an allowed project. Chat, high-level task planning and persisted review remain available.
- Native `desktop/`: Tauri/React/TypeScript with Rust in-memory credentials and verified HTTPS, bounded API/SSE, scoped stream IDs/cancellation, encoded-path escape rejection, truthful MAC/BACKEND model status and deployment capability gates. File pane read-only; approved command runner, no full editor or PTY.
- Browser dashboard: owner cookie sign-in/sign-out, password input cleared, no browser credential storage, restricted controls follow server capability. Static CSP/local assets retained.
- `deploy/`: Docker/Compose/environment/LaunchAgent/ACL **review templates only**, source build-context allowlist; read-only `scripts/deployment_preflight.py`. No Docker on Mac: static property/preflight tests are not actual container integration.

## Verification

- Final HTTP-enabled Python suite: **219 discovered, 215 executed/passed, 0 failed/errors, 4 skipped**, 53.607 s.
- Final default Python suite with authorized local-socket access: **219 discovered, 171 executed/passed, 0 failed/errors, 48 skipped**, 20.316 s.
- Seven Vitest tests passed (two files); three Rust tests passed; TypeScript/Vite production build and optimized Tauri app build passed (Rust release compilation 28.03 s, bundle about 12.91 MiB).
- Python compile, browser JS syntax, prepared JSON/plist parse, dashboard static contracts and Git diff whitespace checks passed. Strict deep codesign verification passed after ad-hoc signing the new output bundle.
- Four full-profile skips: three optional disabled Respan dependency tests and one Linux /proc observation test on macOS. Default skips 44 additional opt-in local HTTP tests. No tests removed or weakened.
- Final targeted changed-policy tests: eight proxy/profile tests passed; worker tests 17 passed; six deployment/rotation tests passed. These counts are subsets of the complete suite, not additional independent coverage.

Real installed `qwen2.5-coder:14b`, outbound-worker HTTP bridge: **17/17 checks passed in 82,764 ms**. Synthetic authenticated chat → scoped worktree → approved hash-bound patch → actual `Ran 1 test` / exit 0 → evidence-checked completion → restart persistence, no invocation replay or private code. First fixture attempt failed safely because the generated test command mismatched the previous layout; failed evidence is retained separately, fixture corrected and rerun passed. Earlier direct-loopback Qwen evidence remains historical.

Rebuilt optimized native app manually verified via CUA against a disposable authenticated backend + real installed Gemma worker: invalid auth 401, valid owner, actual installed model MAC location, real streamed response (about 2.4 s), actual Stop generation with stopped/display-only persisted partial text, execution controls disabled and disconnect clears prior state. Browser invalid/valid owner login, rendered state, disabled worktree/command/Git controls and sign-out back to login were manually verified. Synthetic DB shows worker statuses complete/cancelled and no retained job payload. This is manual local UI evidence, not JARVIS HTTPS or automated native integration coverage. Transient capture failures recovered by reselecting app.

Failures fixed during AFK: two stalled-socket cancellation assertions, macOS resolved-path expectation, worker log recreation permissions, Unicode control-envelope sizing, disabled proposal/patch routes and persisted root revalidation. One default run inside restricted socket sandbox had 37 environmental errors and 44 skips; rerunning with authorized loopback access passed. Preserve logs; do not count that failed invocation as a successful run.

## Build and local environment

Mac Python 3.13 / Node 24 available. Existing npm dependencies and previously approved isolated Rust 1.99.1 used, no server installation. For Rust/Tauri:

```sh
export CARGO_HOME=/Users/macbramesha/Documents/Codex/2026-11-07/files-pasted-by-the-user-personal/work/toolchain/cargo
export RUSTUP_HOME=/Users/macbramesha/Documents/Codex/2026-11-07/files-pasted-by-the-user-personal/work/toolchain/rustup
export PATH="$CARGO_HOME/bin:$PATH"
# from desktop/: npm run build && npm test
# cargo test --manifest-path src-tauri/Cargo.toml --locked -j 2
# CARGO_BUILD_JOBS=2 npm run tauri -- build --bundles app
```

Tests must use disposable data, e.g. `PERSONAL_CODEX_DATA="$PWD/work/tests/data" PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v`. Both profiles include some pre-existing local-socket tests even without HTTP flag; use authorized loopback sandbox access. Default skips optional HTTP tests; full HTTP still skips optional gateway dependency (3) and Linux /proc child observation on macOS (1).

Deliverables/evidence live at `/Users/macbramesha/Documents/Codex/2026-11-07/files-pasted-by-the-user-personal/outputs`: AFK_REPORT.md, AFK_APPROVAL_QUEUE.md, PRIVATE_DEPLOYMENT_NOTES.md, AFK_ARTIFACTS.json, current source archive, `afk-native/Personal Codex.app` plus zip and UI_EVIDENCE.json, and real worker proof directories. New native app is ad-hoc signed/strictly verified, not notarized. Older app/source/evidence retained. Temporary fixture backend/worker on 8791 stopped; native app left disconnected; original Ollama/Tailscale unchanged.

## Deployment gates and exact next action

Read `DEPLOYMENT.md`, `docs/API.md`, `docs/IMPLEMENTATION_MATRIX.md` and the private review queue. Initial candidate uses host-network nonroot Docker to reach the existing host-loopback Serve backend, read-only rootfs/cap drops/no-new-privileges/CPU-memory-PID/tmpfs/log bounds, no Docker socket/family mounts. Host networking shares host namespace and gives no egress isolation. Directory mounts refuse implicit creation. Need actual target Docker/Compose/version/image-digest/constraints checks; no production certification.

Storage: preserve >=200 decimal GB free, <=75 GB total application allocation; template data budget 74 GB leaves 1 GB overhead. Readiness and snapshots measure usage, **not hard quota enforcement**. Hard quota, actual image/source/log accounting, automated monitoring and backup scheduling remain unresolved approval-dependent work. Do not enable global filesystem options or delete data to make room.

1. Wait for an actual access/approval change, then refresh only authorised read-only server metadata and existing Serve configuration. No repeated failed SSH or personal directory scan.
2. Review exact dedicated directory, nonroot UID/GID, pinned image/size, project roots, storage/quota and existing full ACL/family-app dependencies. No placeholder identity or assumed Docker permission.
3. Obtain explicit approval before server directories/tokens/image install/service startup, Serve modification, full ACL change or persistent Mac LaunchAgent. Narrow grants do not override existing allow-all; no blind replacement. No Funnel, public ports, router change, Ollama exposure or model download.
4. After approval, execute scoped deployment/preflight and verify actual private HTTPS, unauthorized rejection, MAC worker inference/stream/stop/retry/restart, resources, snapshot/restore and permitted/denied tailnet clients. Record actual evidence.
5. Keep code proposals/patches/commands/Git disabled on JARVIS until an approved OS execution/egress sandbox is implemented and tested. This is a separate prerequisite for full coding Mission 1.

Safe independent future work: design a concrete OS containment boundary for review, portable Linux CI without private secrets, automated native end-to-end coverage and reviewed metadata archival. Do not add speculative services or downloads to fill approval gaps. No pending routine local regression failure is known; remaining production gaps are explicit above.
