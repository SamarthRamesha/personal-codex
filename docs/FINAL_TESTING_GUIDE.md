# Personal Codex owner testing guide

## Download and launch on the M3

1. Open the integration workflow runs and choose the newest successful run for the commit you want to test. Download the artifact named `Personal-Codex-macOS-ARM64-<commit>`. Keep its commit ID and use a separate source checkout at that exact commit. [Integration workflow runs](https://github.com/SamarthRamesha/personal-codex/actions?query=branch%3Apersonal-codex%2Fcodex-integration)
2. Extract the artifact into a new folder. From that folder run `shasum -a 256 -c Personal-Codex-macOS.sha256` if the checksum file is included. Extract the inner `Personal-Codex-macOS.zip` there. Keep the installed, permission-approved Automation Preview in its current location.
3. On macOS 14 or later, have Python 3.11+, Git, Ollama and at least one of `qwen3.5:9b` or `qwen2.5-coder:14b` already installed. If you downloaded the app, verify it with `codesign --verify --deep --strict "/absolute/path/Personal Codex.app"`. If macOS blocks the downloaded build, use the separate local source build documented below. The bundle is ad-hoc signed and still needs owner acceptance.
4. From the matching source checkout, start an isolated profile:

   ```sh
   python3 scripts/offline_workstation.py --data-dir "$PWD/data/release-candidate" \
     --app "/absolute/path/Personal Codex.app"
   ```

   Pass `--model qwen2.5-coder:14b` to select that cached model at launch. Click **Connect backend** in the app. Keep the terminal open. [Source build and startup](GETTING_STARTED.md)

## Run the acceptance checklist

- **Conversation.** Start a chat and watch a response stream. Stop a long response and regenerate it. If both supported models are installed, use the provider selector to regenerate with the other model. Restart the candidate and check that both conversation content and search work. Try pin, rename, archive and restore.
- **Project.** Open a disposable Git repository through the Projects sidebar. Open **Project memory** and save and correct a harmless convention. Verify that your correction appears as an owner note. If testing document context, attach a disposable text file, index it under **Project documents**, and check the excerpt before using it.
- **Coding.** Choose **Create coding task** and describe a small behavior plus the expected test. Request and approve the isolated worktree. Request and approve the planning call, generate the proposal, review its files and commands, then separately approve execution. Compare the operation ledger, test exit status and output. Discard a proposal that is stale or unsuitable, give revised instructions if useful, then request a fresh round. After cancellation or interruption, request a fresh round and approve it again. A stopped **Full task execution** can resume explicitly within its original scope.
- **Dependencies and preview.** Once a worktree is ready, **Task worktree readiness** shows its dependency markers, declared checks and declared server commands. Copy the displayed directory and use a dedicated terminal there. Review the exact install command and any project lifecycle scripts before personally running it. Refresh the report afterward. For a dev server, review the script and its bind address, start it in the foreground and stop it with Ctrl+C in that terminal. Install and server commands stay under your terminal's control. For a supported declared npm check, use **Review check** to fill the runner. Request, review and approve the exact command before running it.
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

- **Startup.** If ports 11434 or 8787 are occupied, use the existing application's normal controls or leave it running and defer acceptance. Review the launcher-printed log directory for the owned Ollama and backend logs. For missing models, check `ollama list`.
- **Coding.** If a proposal is rejected or an approval expires, read the exact error and request a fresh proposal or approval. Keep a failed or conflicting worktree for inspection. Setup and preview commands may need project-specific tools, network access or configuration in your terminal.
- **Rollback.** Quit the candidate and stop its launcher. Start the previous bundle with its matching source checkout and original profile. Leave the candidate profile, data and worktrees available for diagnosis. Keep the previous automation bundle and its permission settings.

## Acceptance and JARVIS

Hosted builds use scripted inference for calculator and resume checks. Real Ollama, native windows, OCR, browser isolation and local-model automation still need acceptance on the owner's M3 for this release. The JARVIS host is reported online. The prepared integration supports a private HTTPS backend and an outbound Mac model worker with separate credentials. Deployment and target readiness remain unverified in this session. Keep using the local candidate independently. [Deployment and approval plan](../DEPLOYMENT.md)
