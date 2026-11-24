# Personal Codex for Mac

Native Tauri 2 + React + TypeScript client. Hosted chat products are not runtime dependencies. Start with the repository [getting-started guide](../docs/GETTING_STARTED.md).

## Run and build

On the prepared Mac, `python3 scripts/offline_workstation.py` starts the loopback services and prefers the standard release bundle when present. A preexisting service on the reserved ports is preserved and reported as a conflict. Local inference uses the existing Ollama cache.

```sh
cd desktop
npm ci --ignore-scripts
npm test
APPLE_SIGNING_IDENTITY=- npm run tauri -- build --ci --bundles app -- --locked
```

The frontend development preview (`npm run dev`) connects only through its loopback proxy and cannot verify native IPC. Local bundles are ad-hoc signed, not notarized; they and private profiles remain outside Git.

## Implemented interface

- Conversations, persisted streaming history, model selection/details and observed inference metrics.
- Finder-selected projects and attachments, full-task planning/repair/checks/delivery, exact review/diffs and explicit resume.
- Selected project-document search with source attribution, explicit index/update/remove and untrusted-reference labels.
- Local **Mac actions** for reviewed installed-app/document opening and Finder reveal, available even without connecting a backend.
- Authenticated backend connection, cancellation/reconnect, diagnostics and verified SQLite snapshots.

See [Mac actions](../docs/MAC_ACTIONS.md) for its separate local consent boundary and unverified visual acceptance. It does not provide general cross-app automation.

## Connection and permissions

The native bridge accepts loopback HTTP(S) or verified HTTPS at a `.ts.net` hostname. The proposed production path uses standard HTTPS through Tailscale Serve with a loopback-only backend; the older direct-TLS port mode is optional. There is no certificate override, redirect following or proxy-environment fallback.

Owner credentials stay in native process memory. The managed offline launch reads its existing owner-only token file; manual remote connections take a token explicitly and do not save it in browser storage. Disconnect clears connection authority. Slow handshakes and streams are bound to their connection generation. Mutations are not silently retried.

Mac actions are local named IPC commands, independent of backend authority; no remote HTTP endpoint exists. A server response/model message cannot invoke them. No filesystem/shell/HTTP Tauri plugins or remote content scripts are enabled. The Mac opening boundary does not enable Accessibility, Automation, screen capture or system-wide file reading.

## Current limits and evidence

14frontend tests,7 Rust tests, TypeScript/Vite and optimized native build pass. Earlier chat/stream/stop/files/task/native authentication and document-search UI checks were performed on the Mac. The newest Mac opening panel's visual verification was blocked by the UI connector; app builds are not UI acceptance.

JARVIS is not deployed; actual remote HTTPS/worker/reconnect/sleep/server restart and denied-client acceptance remain pending. General editor/PTY, autonomous cross-app interaction, broad browser control, notarized distribution and auto-updates remain open. [Current status](../docs/IMPLEMENTATION_MATRIX.md).
