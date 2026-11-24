# Getting started

## Prepared Mac

1. Open a terminal in the repository and run `python3 scripts/offline_workstation.py`.
2. Choose **Connect backend**. Local mode authenticates from its private owner file.
3. Choose an installed model and start a conversation. The latest answer can be stopped or regenerated with a different installed model.
4. Open a Git project and choose **Create coding task** in its workspace. Request and approve the task worktree, then request and approve local inference for a proposal.
5. Review the proposed changes and separately approve execution. Inspect the running operations, command output and test results. Request a fresh round after a failed or interrupted round.
6. Once the task is complete, review and commit the intended files in the worktree shown under **Deliver changes**. Request release, then review and approve the exact merge into the project. Reopen the task from project history to see its saved result.

**Full task execution** authorizes a bounded local run that can deliver after checks pass. Choose the
destination and review the scope before authorizing it. This mode supports explicit resume within
the original scope. **Project memory** shows saved notes and evidence from completed rounds before
you decide whether to save a proposed note.

The launcher picks the standard release bundle in `desktop/src-tauri/target/release/bundle/macos/` first. Use `--app` to select a specific bundle. It needs the Ollama CLI and either `qwen3.5:9b` or `qwen2.5-coder:14b` already cached. It selects the first installed model in that order unless you pass `--model`. If port 11434 or 8787 is occupied, quit the existing service through its normal controls before launching.

## Mac opening actions

Open the built native app. If the connection screen is visible, close it, then choose **Mac actions** in the sidebar. This panel does not need a backend.

- Search for an installed app and select it.
- Or choose a document, file or folder through Finder.
- Read the full destination and choose **Confirm and open**.

The review expires after two minutes and can be used only once. macOS can still deny the request or ask for its own permissions. A successful receipt means macOS accepted the open request; it does not verify a larger workflow. See [Mac actions](MAC_ACTIONS.md).

## Build the native application

On macOS 14 or later, use Python 3.11+, Git, Node 22+, Rust/Cargo and Apple's Command Line Tools. Build in a separate checkout so the installed Automation Preview and its permissions stay intact.

```sh
cd desktop
npm ci --ignore-scripts
npm test
APPLE_SIGNING_IDENTITY=- npm run tauri -- build --ci --bundles app -- --locked
```

The output is under `desktop/src-tauri/target/release/bundle/macos/`. Local ad-hoc signatures are not notarized distribution. Keep the previous bundle and a verified database snapshot when changing versions; do not bypass macOS security warnings.

On a successful integration run with an uploaded candidate, download the artifact matching your
Mac's architecture (`ARM64` for the M3), unpack `Personal-Codex-macOS.zip` into a separate folder,
and pass the extracted app to `--app`. The artifact expires after 14 days. Use the checkout matching
the artifact's commit for the launcher and backend. The included calculator receipt uses scripted
inference. Interactive Mac acceptance and a live-model run remain separate checks.

From the repository root, launch the candidate against an isolated profile for your first test:

```sh
python3 scripts/offline_workstation.py --data-dir "$PWD/data/release-candidate" \
  --app "$PWD/desktop/src-tauri/target/release/bundle/macos/Personal Codex.app"
```

Add `--project-root /absolute/path/to/test-repositories` to use an existing dedicated
repository directory. Without it, the launcher manages projects under the candidate profile.
To roll back, quit the candidate and launch the previous checkout's launcher with its matching
bundle and original profile. Keep the candidate profile and its worktrees for inspection.

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
