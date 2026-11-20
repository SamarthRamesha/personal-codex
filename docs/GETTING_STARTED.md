# Getting started

## Prepared Mac

1. Open a terminal in the repository and run `python3 scripts/offline_workstation.py`.
2. Choose **Connect backend**. Local mode authenticates from its private owner file.
3. Choose the installed model, create a conversation, or open **Full task execution**.
4. For coding, choose an existing Git project or a parent folder for a new one. Describe the behavior and a concrete example. Attach only the references you want included.
5. Review the destination and authorize the bounded task. Inspect the actual checks and delivered files. Stop saves completed work; resume is explicit.

The latest local bundle lives in `data/mac-actions-app/Personal Codex.app` when built. Previous bundles and profiles remain available. App bundles are not committed to Git. The launcher needs an installed Ollama binary and the selected model already cached. It does not download a model. If its ports are occupied, use the existing service's normal controls yourself; the launcher never kills it.

## Mac opening actions

Open the built native app. If the connection screen is visible, close it, then choose **Mac actions** in the sidebar. This panel does not need a backend.

- Search for an installed app and select it.
- Or choose a document, file or folder through Finder.
- Read the full destination and choose **Confirm and open**.

The review expires after two minutes and can be used only once. macOS can still deny the request or ask for its own permissions. A successful receipt means macOS accepted the open request; it does not verify a larger workflow. See [Mac actions](MAC_ACTIONS.md).

## Build the native application

Install the normal vendor toolchains: Python 3.11+ (3.13 tested), Git, Node 22+, Rust/Cargo and Apple's Command Line Tools. Ollama is required only for local inference. Do not install optional gateway/recovery packages unless you need and approve that feature.

```sh
cd desktop
npm ci
npm test
npm run build
cargo test --locked --manifest-path src-tauri/Cargo.toml -j 2
npm run tauri -- build --bundles app
```

The output is under `desktop/src-tauri/target/release/bundle/macos/`. Local ad-hoc signatures are not notarized distribution. Keep the previous bundle and a verified database snapshot when changing versions; do not bypass macOS security warnings.

On another Mac, supply the built bundle to the launcher:

```sh
python3 scripts/offline_workstation.py --app '/absolute/path/Personal Codex.app'
```

## Backend development preview

```sh
python3 app/server.py
```

Open the loopback dashboard at `http://127.0.0.1:8787`. A bare loopback development launch may be unauthenticated; use the authenticated launcher for the prepared native offline workflow. Do not expose the development listener to the network. The native development preview is `cd desktop && npm run dev`; it does not exercise native IPC or remote authentication.

## Home-server connection

The intended path is a separately deployed authenticated backend behind private Tailscale HTTPS, with an outbound Mac inference worker. It is not installed on JARVIS yet. Entering a server URL cannot install it. Do not copy local tokens into a public repository, substitute insecure HTTP, disable certificate checks or expose Ollama. See [deployment](../DEPLOYMENT.md).

## When something stops

- A missing model or dependency is reported; no silent cloud fallback or download occurs.
- A conflicting edit prevents delivery and leaves the task worktree intact.
- A stopped/interrupted task requires explicit resume within its original scope.
- An expired Mac action must be reviewed again; check whether an uncertain open request already succeeded before retrying.
- A server outage does not turn remote acceptance into success. Keep the local profile and last working app.
