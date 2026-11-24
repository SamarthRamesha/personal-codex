# Personal Codex release candidate · Session 2

Continue from the published tip of `personal-codex/codex-integration`. The Session 1 merge
`a98ec00` contains both `c23411b` (Codex) and `4e27eb2` (Freebuff). Verify the remote tip and
read [the integration record](docs/AGENT_COORDINATION_CODEX.md), [getting started](docs/GETTING_STARTED.md),
[the Mac acceptance runbook](docs/MAC_ACCEPTANCE_RUNBOOK.md) and [the risk register](docs/RISK_REGISTER.md).

## Preserve

- Commit and push only to `personal-codex/codex-integration`, explicitly. Leave `main` and R-36
  for the owner. Preserve Git history, owner changes and private files.
- Never read, stage, modify, delete or upload `personal-codex-diagnostic.txt`. Preserve
  `web/style.css`, `web/chat.js`, `.recovery-backup/`, `.safety/`, `diagnostics/`,
  `SESSION_HANDOFF.md`, installed models and user profiles.
- Keep the installed permission-approved Automation Preview in place. Use a separate checkout,
  candidate, data profile and synthetic fixtures. Only the owner grants native permissions.
- JARVIS is reported offline and remains outside scope.

## First priority on the M3

1. Use the published candidate build or build the same commit in a separate checkout. Follow the
   exact startup commands in [getting started](docs/GETTING_STARTED.md). Launch with the isolated
   `data/release-candidate` profile and a supported cached Ollama model. Connect and test startup,
   file selection, generation, stop, regeneration and continuation with real inference.
2. Work through the reviewed coding flow on a disposable Git repository. Inspect the rendered
   plan, approve the exact round, observe work and tests, review the resulting files, commit them
   in the task worktree, then separately approve release and merge. Verify saved results after
   restarting. Test an interrupted task and the fresh-round or explicit full-resume path.
3. Run the live calculator acceptance with an installed `qwen3.5:9b` served on loopback and an
   unused output directory. From the source checkout run
   `mkdir -p work` and
   `python3 scripts/full_task_acceptance.py --live --existing --output "$PWD/work/session2-live-calculator"`.
   Keep the receipt and independently validate the destination files. The default script and CI
   fixture use scripted inference.
4. Run the interactive gates in the Mac acceptance runbook with owner-approved permissions and
   synthetic input. Capture/OCR, browser-window isolation and the historical scrollbar case need
   explicit evidence. Record exactly which stages ran and fix any observed failures.
5. Reproduce the build and rollback instructions. Work on demonstrated release blockers before
   adding breadth. Broader stack installation/dev-server management, notarization and update
   distribution remain open.

## Evidence from Session 1

- Local Linux HTTP suite ran 466 tests with four skips. The frontend passed 95 tests and
  TypeScript/Vite production build.
- The cloud browser tested an actual disposable Git project against the development backend.
  Scripted inference returned a failed proposal, a repair and a completion. Real Python
  tests exited 1 then 0. After a manual Git commit, the individually approved release
  and merge reached the destination and the status and evidence survived backend restart.
- The same browser tested persisted project memory, archived search refresh, chat stop and
  regeneration with a different scripted local model, and live operation status during a check.
- Hosted integration runs #115 and #116 passed backend, frontend and the Mac job, including native
  policy tests, scripted calculator delivery and app bundling. Run #116 also published an ARM64
  candidate after signature verification. Verify the current commit's run and artifact independently.
  [Run #116](https://github.com/SamarthRamesha/personal-codex/actions/runs/45426866817)
