# Personal Codex: current implementation handoff

Current as of 2026-11-07, Asia/Kolkata. Continue the existing checkout; do not recreate it. Latest AFK autonomy instructions permit ordinary local code, tests, synthetic fixtures, native builds, documentation and local commits. Queue infrastructure approvals and continue independent work. No automatic deployment.

## Repository and preservation

- Repository: `https://github.com/SamarthRamesha/personal-codex`.
- Checkout: `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`.
- Branch: `personal-codex/stabilization`; historical published tip `4a3ea1d91e70e392faf342ea03b335d7f207169d`.
- AFK core milestone `9109eb1`: durable outbound worker, private proxy/runtime and native contract fixes. Further local preparation/handoff commits follow; use `git log -3` for exact current tip. No AFK changes pushed.
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
