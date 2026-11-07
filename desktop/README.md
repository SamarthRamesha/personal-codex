# Personal Codex for Mac

Native Tauri 2 + React + TypeScript client for the existing Python control plane. This is a standalone client: ChatGPT, Codex, Freebuff and hosted AI services are not runtime requirements.

## Run from source

From the repository root, start `python3 app/server.py` for loopback development. In another terminal:

```sh
cd desktop
npm ci
npm run tauri -- dev
```

Requirements: Python 3.11+ for a local backend, Git, Node/npm, Rust/Cargo, and Apple's Command Line Tools. The remote client does not need Python on the Mac; the backend must already be running on the configured server.

The development browser preview (`npm run dev`) proxies `/api` only to `127.0.0.1:8787`. Native authentication and remote connections must be tested in the actual app, not the browser preview.

## Build and check

```sh
npm run build
npm test
npm run tauri -- build --bundles app
cd src-tauri
cargo test --locked -j 2
```

`package-lock.json` and `Cargo.lock` pin resolved dependencies. No HTTP, shell or filesystem Tauri plugin is enabled. Only the named Rust commands can talk to a configured backend. There is no updater or analytics integration.

## Connect

- Local development: `http://127.0.0.1:8787`, token blank unless authentication was configured.
- Authenticated local backend: same URL plus the owner token created through `scripts/private_backend.py`.
- Private server: `https://<actual-hostname>.<actual-tailnet>.ts.net:8787`, a valid trusted certificate for that hostname, and an owner token. The backend must bind its actual Tailscale IP. No public addresses, HTTP remote connection, certificate override, redirects or proxy-environment fallback are supported.

The URL is saved in local browser storage. The token is held in native memory for that connection and is never saved in browser storage or settings. Disconnect clears native credentials and displayed backend data. Manual reconnection to an authenticated backend requires entering the token again. Stream interruptions retry up to four times, with persisted sequence cursors and bounded backoff. Interrupted writes are never automatically retried.

## What is implemented

Conversations, searchable history, project registration and selection, local provider registration, installed Ollama model discovery and selection, real streaming, safe Markdown/code display and copy actions, stop and retry, chat-to-task creation, project file previews, task selection, exact approval review/rejection, operation inspection, unified diffs with stale detection, round execution/history, approved command runner, task cancellation, storage diagnostics and verified database snapshots. Shortcuts: Command-N for new chat, Command-K for search, Command-comma for settings, Enter to send, Shift-Enter for a newline.

## Current boundaries

File previews are read-only; a general code editor and PTY terminal are not implemented. Commands use the existing exact-approval runner. Attachments, image/audio input, reasoning controls, model downloads, native tool calling, project folders, rich Git merge UI and automated app updates are not exposed as working controls. The existing browser dashboard remains available for features without native parity, including memory and merge/recovery controls. Its authenticated cookie API exists; a browser login form is still pending.

Local app launch, persisted history, streaming/stop, files, task evidence, snapshot creation, disconnect/reconnect, owner authentication, missing-token rejection and untrusted-certificate refusal were exercised on the actual Mac. Home-to-ZimaOS and off-Wi-Fi operation are blocked on SSH access and server deployment. A built bundle is not proof of the remote product.

## Packaging and updates

Current bundles are local development releases without an Apple Developer distribution identity or notarization. No credential or signing profile was used. Install by moving a reviewed release bundle yourself; keep the previous bundle and a verified database snapshot for rollback. Do not bypass Gatekeeper warnings or enable automatic downloads. Signed/notarized distribution needs a separate approved signing workflow.

The native IPC stream follows Tauri's [Channel API](https://v2.tauri.app/reference/javascript/api/namespacecore/). Platform setup follows the [official prerequisites](https://tauri.app/start/prerequisites/).
