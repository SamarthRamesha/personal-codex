# Personal Codex owner testing guide

## Download and launch on the M3

1. Open the integration workflow runs and choose the newest successful run for the commit you want to test. Download the artifact named `Personal-Codex-macOS-ARM64-<commit>`. Keep its commit ID. New artifacts include Personal-Codex-source.zip at that exact commit; extract it into a separate directory, or use a matching source checkout. [Integration workflow runs](https://github.com/SamarthRamesha/personal-codex/actions?query=branch%3Apersonal-codex%2Fcodex-integration)
2. Extract the artifact into a new folder. From that folder run `shasum -a 256 -c Personal-Codex-macOS.sha256` if the checksum file is included. Extract the inner `Personal-Codex-macOS.zip` there. Keep the installed, permission-approved Automation Preview in its current location.
3. On macOS 14 or later, have Python 3.11+, Git, Ollama and at least one of `qwen3.5:9b` or `qwen2.5-coder:14b` already installed. If you downloaded the app, verify it with `codesign --verify --deep --strict "/absolute/path/Personal Codex.app"`. If macOS blocks the downloaded build, use the separate local source build documented below. The bundle is ad-hoc signed and still needs owner acceptance.
4. From the matching source checkout, start an isolated profile:

   ```sh
   python3 scripts/offline_workstation.py --data-dir "$PWD/data/release-candidate" \
     --app "/absolute/path/Personal Codex.app"
   ```

   Pass `--model qwen2.5-coder:14b` to select that cached model at launch. If Ollama is already running, add `--reuse-ollama`; its existing lifecycle stays under your control. Click **Connect backend** in the app. Keep the terminal open. [Source build and startup](GETTING_STARTED.md)

## Run the acceptance checklist

- **Conversation.** Start a chat and watch a response stream. Stop a long response and regenerate it. If both supported models are installed, use the provider selector to regenerate with the other model. Restart the candidate and check that both conversation content and search work. Try pin, rename, archive and restore.
- **Project.** Open a disposable Git repository through the Projects sidebar. Open **Project memory** and save and correct a harmless convention. Verify that your correction appears as an owner note. If testing document context, attach a disposable text file, index it under **Project documents**, and check the excerpt before using it.
- **Coding.** Choose **Create coding task** and describe a small behavior plus the expected test. Request and approve the isolated worktree. Request the planning call, inspect **Planning context files** and approve it, then generate the proposal, review its files and commands, then separately approve execution. Compare the operation ledger, test exit status and output. Discard a proposal that is stale or unsuitable, give revised instructions if useful, then request a fresh round. After cancellation or interruption, request a fresh round and approve it again. A stopped **Full task execution** can resume explicitly within its original scope.
- **Dependencies and preview.** Select an approved task worktree. For supported locked npm projects choose **Review locked npm install**, inspect exact packages/URLs/hashes and confirm installation and downloads separately. Wait for completion and refreshed readiness. For a declared plain Node entry use **Review preview start**, confirm the exact scope/port, wait for running, inspect logs, deliberately open/copy the address and stop the owned preview. Other managers/frameworks remain project-specific terminal workflows. Supported declared npm checks can use **Review check**, followed by exact command approval. See the limits below.
- **Delivery.** Independently inspect the worktree diff and run the expected tests. Commit only the intended changes in the task worktree. Under **Deliver changes**, request and approve worktree release, then separately review and approve the exact merge. Verify the destination and reopen the saved task after restarting the candidate.
- **Mac automation.** Use **Mac automation** with the bundled synthetic fixture. Follow the runbook for selected-window actions, permission prompts, one-use approval, capture/OCR and the fresh browser window test. Run the selected-window and browser stages with synthetic content only. Record the exact stage and result. [Mac acceptance runbook](MAC_ACCEPTANCE_RUNBOOK.md)

For a second real-model check, with the launcher-owned Ollama serving on loopback and other requests idle, run the disposable calculator acceptance from a second terminal at the source root. Use an output path that does not exist yet.

```sh
mkdir -p work
python3 scripts/full_task_acceptance.py --live --existing --model qwen3.5:9b \
  --output "$PWD/work/owner-live-calculator"
```

Choose `qwen2.5-coder:14b` instead if that is the cached model. Keep `evidence.json` and independently check the generated calculator and tests.

## Diagnose or roll back

- **Startup.** If ports 11434 or 8787 are occupied, use the existing application's normal controls or leave it running and defer acceptance. Review the launcher-printed log directory for the owned Ollama and backend logs. For missing models, check `ollama list`. For verified registry HTTPS errors, inspect the launcher environment and existing CA configuration; the launcher retains SSL_CERT_FILE/SSL_CERT_DIR. Never disable certificate validation as a workaround.
- **Coding.** If a proposal is rejected or an approval expires, read the exact error and request a fresh proposal or approval. Keep a failed or conflicting worktree for inspection. Setup and preview commands may need project-specific tools, network access or configuration in your terminal.
- **Rollback.** Quit the candidate and stop its launcher. Start the previous bundle with its matching source checkout and original profile. Leave the candidate profile, data and worktrees available for diagnosis. Keep the previous automation bundle and its permission settings.

## Acceptance and JARVIS

Hosted builds use scripted inference for calculator and resume checks. The 28 November Mac session also passed real 9B coding/web fixtures and isolated desktop startup, download, preview and chat checks. Native cross-app actions, OCR, product browser isolation and local-model automation still need owner acceptance. See [evidence and limits](PRODUCT_COMPLETION.md). The JARVIS host is reported online. The prepared integration supports a private HTTPS backend and an outbound Mac model worker with separate credentials. Deployment and target readiness remain unverified in this session. Keep using the local candidate independently. [Deployment and approval plan](../DEPLOYMENT.md)

## Reviewed installs and owned previews

Task readiness now includes reviewed npm installation and managed Node previews. Start with a disposable locked project. Inspect the exact package URLs, file hashes and destination, confirm install and downloads independently, then verify progress and cancellation. Existing node_modules is preserved. See [supported installer and limits](DEPENDENCY_INSTALLATION.md).

For a declared `node server.js` development script, review its exact task scope and a free loopback port. Confirm once, wait for owned HTTP readiness, inspect logs, then deliberately open or copy the preview address. Stop and confirm only that owned listener closes. Restart never replays the start; review again. Outbound connections, new binds and project writes remain denied. See [preview lifecycle and limits](MANAGED_PREVIEWS.md). Vite/general framework commands and write caches remain unimplemented adapters.
