# Next-session implementation handoff

Continue this existing project from the actual repository state. Do not recreate the project or replace functioning components. Read this prompt and the current status/acceptance/threat documents first; verify every claim against code and tests. Preserve user changes and project history. This handoff is current as of 2026-11-07 (Asia/Kolkata).

## Objective and current result

Build Personal Codex into a private, local-first autonomous coding environment: native Mac UI, primary ZimaOS backend/local inference over the user's existing Tailscale network, persistent chat/tasks/memory, approval-controlled coding/worktrees/tests/diffs and robust recovery. No ChatGPT/Codex/Freebuff/hosted model is a runtime dependency. No training on private data, silent cloud fallback, telemetry, public service or unrestricted model shell/filesystem access is permitted.

Mission 1 is **PARTIAL**, not complete. The native client and real Mac local-model workflow work. ZimaOS deployment and genuine home/off-Wi-Fi remote acceptance remain blocked on SSH authentication and actual machine inspection. Continue with that foundation before breadth from Missions 2/3.

## Repository and Git

- Official remote: `https://github.com/SamarthRamesha/personal-codex.git` (`origin`).
- Actual checkout: `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`.
- Active branch: `personal-codex/stabilization`. Do not blindly switch to historical main.
- Session began at `414e0cb`; remote stabilization had advanced to `12a24d59041af2c2a8b1023c40b55a63a660e8e6` (`test: isolate unreachable provider discovery from host state`). Fetched and fast-forwarded; main remained `3ab25b0`.
- Latest implementation commit: `c5e34159faf5c88bcfc1163e37c0ddffffebacce` — `feat(desktop): add authenticated native coding workspace and recovery controls`. This handoff update is a following documentation checkpoint; run `git log -1` for its actual tip. The code milestone was committed with only the pre-existing diagnostic left untracked. Publication is verified separately after the checkpoint push.
- The pre-existing untracked `personal-codex-diagnostic.txt` belongs to the user. Do not read, stage, delete or publish it.
- Do not reset/clean/rebase/force-push, overwrite unexpected changes, merge important branches without authorization or publish private application data. Push completed safe milestones to the existing stabilization branch when authentication/state permit. Remote private host metadata is intentionally absent from Git.

## Architecture

- `app/server.py`: standard-library HTTP API, SQLite Store/schema/additive migrations, immutable digest approvals, projects/tasks/worktrees/Git merge recovery, provider/agent rounds, operation ledger, cancellation/budgets/context/memory, SSE, contained file APIs, connection/diagnostics/backup routes. Backend is authoritative; UI never authorizes itself.
- `app/security.py`: owner-only regular token-file validation with no symlink following; bearer token and hashed in-memory cookie sessions (one-hour TTL, bounded sessions/login throttling); Host/Origin/Sec-Fetch checks; non-loopback binding requires an explicit Tailscale IP plus authentication and TLS. Loopback unauthenticated development mode remains explicit.
- `app/conversations.py`: persistent conversations/messages/chunks; actual streamed tokens; atomic content/resume cursor; newest bounded history; at most one active answer per chat and two total chat generations; cloud chat disabled until separately reviewed consent exists; stop/error text is display-only.
- `app/providers.py`: hardened Ollama and OpenAI-compatible transports/discovery, NDJSON/SSE terminal validation, timeout/size/redirect/proxy protections, redaction. Round streaming now defaults on (`PERSONAL_CODEX_STREAM_PROVIDER=1`). Native provider-tool handling is absent and capability metadata says so.
- `app/gateway.py`: historical optional Respan integration, **disabled by default**. Runtime requires explicit `PERSONAL_CODEX_ENABLE_GATEWAY=1` and a separate `network` approval even though its first hop is local. No external gateway was used this session.
- `app/tools.py`: closed list/read/hash-bound exact patch/approved test protocol, containment, bounded diff review; unmatched patches are now stale. Allowlisting/worktrees are **not** an OS sandbox.
- `app/context.py`: deterministic bounded lexical/docs/symbol context and search, `.gitignore`/secret filtering; walks now prune ignored/generated directories rather than sorting an entire recursive tree.
- `app/maintenance.py`: own-data-only usage/CPU/load diagnostics, free-reserve/quota-checked private SQLite snapshots, integrity/SHA verification, seven-snapshot refusal without deletion, 30-second snapshot budget, restore to new files only.
- `desktop/`: Tauri 2 + React 19 + TypeScript + Vite client; Rust credential/HTTP bridge with verified HTTPS, private URL policy, redirect/proxy refusal, bounded responses/streams, no privileged plugins or updater. JS stores only backend URL, never token. Streaming resumes by persisted cursor with bounded retries; mutations are not retried automatically. Source icon is original SVG.
- `web/`: existing dependency-free dashboard retained, including features without native parity. Cookie API exists but browser login UI is pending.
- `PERSONAL_CODEX_DATA` selects a dedicated backend data root; defaults to repo `data/`, fully Git-ignored. SQLite default filename `personal_codex.db`.

## Completed in this milestone

Native Mac app with conversations/history/search, projects, actual local-provider/model discovery and selection, real Markdown/code streaming, copy/stop/retry, chat-to-task, safe file previews, task/proposal/operation/diff inspection, exact approval decisions, approved command execution, cancellation, round/test evidence, diagnostics and snapshot controls. File pane is read-only and terminal is an approved command runner; no general editor or PTY exists.

Added application auth/private TLS listener policy, object/body/framing limits, browser origin/rebinding defenses and method/status-only HTTP logs. Removed chat's self-created cloud approvals, disabled external gateway by default, corrected unverified native-tool capabilities. Fixed atomic approval races, proposal/round claim rollback, cancellation arriving during provider planning, history truncation, duplicate chat sends, atomic stream cursors and stale diff presentation. Native disconnect clears credentials and prior backend selections/data; failed reconnection leaves no fallback connection.

Verified database snapshot/restore, capacity/retention failures and symlink/corruption handling. No auto-deletion, model download, vector database or additional inference engine was added.

## Exact files changed

Application: `.gitignore`, `app/context.py`, `app/conversations.py`, `app/server.py`, `app/tools.py`, new `app/security.py`, `app/maintenance.py`.
Scripts: `scripts/gateway_check.py`, new `inspect_host.sh`, `live_coding_check.py`, `private_backend.py`, `restore_database.py`.
Tests: `tests/test_conversations.py`, `test_gateway.py`, `test_interaction.py`, `test_server.py`, new `test_security.py`, `test_maintenance.py`.
Native: `desktop/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `README.md`, `app-icon.svg`, `src/App.tsx`, `src/api.ts`, `src/api.test.ts`, `src/main.tsx`, `src/style.css`, `src-tauri/Cargo.toml`, `Cargo.lock`, `build.rs`, `tauri.conf.json`, `capabilities/default.json`, `src/main.rs`, generated Mac PNG/ICNS icon files. Build products/node_modules/toolchains are not tracked.
Docs: `README.md`, `PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `SECURITY.md`, `DEPLOYMENT.md`, `HANDOFF.md`, `CHANGELOG.md`, `DEVELOPMENT_LOG.md`, this handoff, new `docs/MISSION_1_ACCEPTANCE.md`, `docs/THREAT_MODEL.md`. Prior milestone documentation is preserved as historical sections.

## Tests and genuine integration evidence

- Reconciled baseline: 156 tests discovered, HTTP-enabled OK with 4 skips.
- Final: `PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v` → 177 discovered, 173 executed, OK (skipped=4), 46.327 s.
- Default: `python3 -m unittest discover -s tests -v` → 177 discovered, 143 executed, OK (skipped=34), 20.701 s.
- Skips: optional gateway dependency absent (3), Linux `/proc` process test inapplicable on macOS (1); default additionally skips opt-in listeners (30). No test was removed/weakened.
- `python3 -m py_compile app/*.py scripts/*.py`, `node --check web/app.js`, `git diff --check` passed.
- `cd desktop && npm run build && npm test` → TypeScript/Vite production build and 2 Vitest SSE-framing tests passed.
- `cd desktop/src-tauri && cargo test --locked -j 2` → 1 native URL-policy test passed. No lint suite is configured.
- Debug and optimized native app bundles built. Optimized release build: 3m 28s, reported 12.92 MiB. Delivered app received an ad-hoc local signature; strict codesign verification passed. No Apple distribution identity or notarization.
- Real installed `llama3.2:3b`: JSON probe 5,186 ms; streaming 2,031 ms / 23 chunks / 103 bytes; chat and patch/tests passed, but it repeated work instead of concluding. Record as PARTIAL.
- Real installed `qwen2.5-coder:14b`: authenticated chat → approved fixture worktree → read/patch/test proposal → current digest-bound diff → separate approval → actual patch/test exit 0 → model completion accepted by evidence → conversation/task persistence after Store restart, all passed. Total 110,671 ms; proposal invocation 65,546 ms. One tiny synthetic fixture, not a model benchmark/server certification. No private repository was sent. No models were downloaded.
- Actual native UI via CUA: launch, persisted history, a real streamed answer, stop, file preview, task/round/test/diff display, snapshot count 0→1, disconnect/reconnect, missing-token HTTP 401, valid synthetic owner auth, self-signed TLS refusal with no fallback, cleared prior data. Corrected issues found during review; optimized release launch inspected too. UI checks are manual evidence, not automated regression coverage.

Full machine-local evidence/artifacts: `/Users/macbramesha/Documents/Codex/2026-11-07/files-pasted-by-the-user-personal/outputs`. Preserve the failed fixture evidence separately from the successful Qwen evidence. Do not publish databases, private deployment notes or diagnostics to GitHub.

## Current services / hardware / access

Mac: Apple Silicon arm64 (user-provided M3/16 GB); macOS 26.6; Python 3.13.9; Node 24.22.1; Command Line Tools installed. Cargo/Rust initially absent; user approved project dependencies and a project-isolated toolchain. Rust 1.99.1 installed at `/Users/macbramesha/Documents/Codex/2026-11-07/files-pasted-by-the-user-personal/work/toolchain/{cargo,rustup}` without shell/global changes. Add that Cargo bin directory to PATH and set CARGO_HOME/RUSTUP_HOME for builds; prefer two jobs. Mac free storage remained roughly 70–73 GB during work.

Existing Ollama and Tailscale services were discovered and left untouched. Installed Mac models: llama3.2:3b (2.0 GB), qwen2.5-coder:14b (9.0 GB), gemma3:1b (815 MB). Their existence is not a recommendation to install them on ZimaOS. Tokens/s, peak RAM/pressure and model concurrency are unmeasured. No inference engine/model was installed.

Tailscale Running; user-confirmed Linux home server online/active with a private route. User supplied exact SSH username/IP and `/DATA` home; exact targets are in local-only `PRIVATE_DEPLOYMENT_NOTES.md` outside Git, or rediscover through authorized Tailscale status. SSH with existing trust and BatchMode reached the host but was rejected (publickey,password). No server inventory, install, configuration change, backup access or deployment occurred. No tailnet/ACL/router changes were authorized.

Temporary UI fixture backends on 8787/8788/8789 were stopped. The delivered native app was left open, disconnected. No Personal Codex production service is installed or running. Existing Ollama/Tailscale services remain as found.

## Remaining risks and blockers

SSH access is the immediate Mission 1 blocker. Actual ZimaOS CPU/ISA/RAM/GPU/OS/filesystem/services/model footprint remain unknown, so no server runtime/model has been selected. TLS hostname certificate provisioning and service install require review/approval; do not bypass certificate validation or substitute public exposure.

Other incomplete items: OS-level filesystem/network sandboxing (approved tests still execute host-accessible code), multi-user/project-scoped auth, bounded global task scheduler, comprehensive quotas including external model storage, server supervision/scheduled backups, editor/PTY, attachments/audio/image/reasoning capabilities, native memory/Git parity, provider-native tools, retrieval benchmarks, signed/notarized distribution and update strategy. Optional features must not displace core remote acceptance. No training on private data.

Resource policy: at least 200 GB free and an initial 75 GB total app/models/caches/logs/data allocation on the shared server. Code defaults to 200 GB reserve on Linux, 5 GB on Mac, and 75 GB owned-data budget. Diagnostics only count the dedicated data root; external Ollama weights must be measured and subtracted from the total allocation before deployment. No broad cleanup or family-backup changes, ever. Storage override values do not authorize exceeding the user's budget.

## Exact next steps

1. Verify Git/status/remotes and the latest checkpoint; do not discard the untracked diagnostic. Read acceptance/threat/deployment/native docs.
2. Check whether the user has established SSH login. Do not ask for passwords/private keys in chat or modify login/security settings. Use the confirmed values in local private notes or authorized discovery.
3. Run `scripts/inspect_host.sh` through authorized SSH, read-only. It avoids `/DATA` traversal and backups. If access still fails, preserve the exact blocker and continue independent work.
4. Measure actual hardware/storage/services, count existing model footprint, confirm dedicated app storage/reserve. Do not install Docker/inference or pull models before this.
5. Prepare concrete dedicated-account/storage/service/certificate/containment changes for review; request approval before server writes, installs, credentials, security settings or resource-limit exceptions. Preserve existing Tailscale ACLs/config and backups.
6. Deploy authenticated verified TLS only after approval; verify native hostname identity, invalid auth, downtime, interruption/reconnection at home/off-Wi-Fi. Then complete real native→ZimaOS→local-model→approved patch/test→persisted result acceptance and record performance.
7. Continue native parity and OS execution/egress isolation, then controlled multi-agent scheduling and reliability finish. Never present unverified controls as working.
8. Update all checkpoint docs and regenerate this handoff after every meaningful verified milestone. Commit/push safe completed work; preserve unpushed commits if unavailable.

## Resume commands

```sh
cd /Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex
git status --short --branch
git log -8 --oneline
git remote -v
python3 -m unittest discover -s tests -v
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v
python3 -m py_compile app/*.py scripts/*.py
node --check web/app.js
python3 app/server.py
# Separate terminal:
cd desktop
npm ci
npm run build
npm test
npm run tauri -- dev
```

`python3 scripts/live_coding_check.py --model <exact-installed-local-model> --output <new-owned-directory>` repeats only the synthetic local fixture. It intentionally refuses to approve arbitrary model edits/commands and retains failed evidence. Treat fixture auto-approvals as a constrained diagnostic, not human approval or remote acceptance.

## Security / permission constraints

User allows ordinary reversible code/tests/docs and explicitly approved project dependency downloads plus the isolated Rust toolchain. User authorized **read-only SSH inspection only** on the home server. Do not install/modify server software/configuration, use new credentials, touch backups, change network/tailnet settings, exceed budgets, merge/delete important branches or perform destructive/irreversible actions without explicit approval. Do not repeatedly ask permission already granted. Keep tokens/passwords/keys and exact private deployment inventory out of logs/Git/publications. Registered project data stays in the user's controlled environment; only explicit reviewed network approvals authorize optional cloud task calls. Cloud chat and external gateway remain off by default.

## PERMANENT CROSS-ACCOUNT CONTINUATION PROTOCOL

This protocol is permanent and recursive. Every future session/account/agent must inspect actual Git, code and tests; preserve history/user changes; regenerate `NEXT_SESSION_PROMPT.md` after each meaningful verified milestone, at the end of every development phase/request, whenever the user requests a handoff/account switch, and before usage exhaustion. Each replacement must remain self-contained and carry this same obligation forward. Never merely append an obsolete prompt or rely on hidden chat history.

Every handoff must include objective; actual architecture; repository/branch/latest verified commit and uncommitted state; completed work and exact changed files; commands/tests/results/skips; dependencies and hardware observations; running services; known issues/access blockers; prioritized next implementation steps; security/approval/resource constraints; Git/publication status and this protocol. Never include credentials or private diagnostic dumps. On an explicit handoff request, stop starting new work, save/test/document the checkpoint, commit/push when authorized/available and display the complete copyable prompt. In ordinary development continue meaningful implementation after a checkpoint while access/budget permit. Keep README and all status/security/deployment/history documents honest about implemented, tested, partial and blocked work.
