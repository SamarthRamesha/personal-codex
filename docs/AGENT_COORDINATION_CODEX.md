# Codex integration coordination

Updated 24 November 2026. Codex owns `personal-codex/codex-integration` in a separate Mac worktree. Freebuff owns `personal-codex/freebuff-implementation`; neither agent rewrites the other's branch. Stable main and draft PR #2 remain unmerged.

## Verified baseline

Base: `f6224e26fc956c07fc0082df6bb4f956d78492a3` from `origin/personal-codex/mac-automation`. Hosted runs 45144435009 and 45144424575 succeeded. This host is macOS 26.6, with Swift/Xcode command-line tools and the cached isolated Rust toolchain. Older Linux-only environment and symbolic-ref publishing instructions are historical and do not apply here. Use normal Git in this isolated worktree.

On this Mac: 422 backend tests passed with five named skips (three optional gateway, Linux /proc child check, disposable Linux syscall filter); 41 frontend tests and the production build passed; 42 Swift helper checks and 13 Rust tests passed (one explicit installed-model test ignored). The first restricted backend run denied loopback listeners; the authorized disposable-listener run passed. No installed app or owner service changed.

## Current ownership and progress

Codex is investigating shared lifecycle/security boundaries in `app/server.py`, workspace file policy, recovery and protocol transport, with focused synthetic regressions. Freebuff's user-facing work is left to its branch. Avoid overlapping implementation without reviewing its published coordination note.

First correction: legacy `/agent/execute` only passed cancellation to its command runner, so file writes ignored task cancellation and shutdown between operations. Three real-HTTP negative controls reproduced writes after stop. The route now passes a stop callback to every operation, keeps completed edits, records `cancelled` and refuses replay. Six focused HTTP tests pass (three new and three existing proposal lifecycle checks).

## Freebuff review record

At initial fetch, `origin/personal-codex/freebuff-implementation` exists at stable `64189ef`, with no new implementation batch. `docs/AGENT_COORDINATION_FREEBUFF.md` is not present in the integration baseline. No Freebuff batch has been integrated into this branch. Earlier work already present in f6224e2 is baseline history, not newly integrated work.

## Native acceptance and preservation

The historical owner screenshots on 21 November show eight passing native checks and one scrollbar failure for the older a6090d7 preview. They do not accept the newer f6224e2 helper. Preserve the installed permission-approved preview and its code identity; build candidates only in this worktree. Do not edit TCC, grant parent apps, overwrite the preview, use personal windows, or change JARVIS. A native build/self-test is not interactive acceptance.

## Next work

Continue approval/execution cancellation and replay safety, sensitive-file boundaries, restart/delivery integrity and real integration tests. Review Freebuff's published branch periodically; inspect diffs and tests before integration. Keep current test/CI and commit evidence here and in the private session checkpoint. Do not stop merely because this first correction passes.

## Shared sensitive-file policy

Direct workspace read/list/patch tools used an older filename list than context selection, so a model could request files that context deliberately omitted. Synthetic negative controls reproduced reads, listing and modification of secrets.json, credentials YAML/TOML, key material and .netrc. `app/file_policy.py` now supplies the common conservative component predicate to both boundaries; listings also omit secret-shaped directories. Ordinary secret_parser.py remains readable. Focused tool/context regressions pass; the installed preview and user data are untouched. This is filename screening, not complete content DLP.

## Process-group cancellation

A resistant child kept writing after its cooperative parent exited on SIGTERM. Cleanup previously returned as soon as the leader was reaped. The new bounded group check waits only the grace period and then kills surviving members. A black-box heartbeat regression failed on the previous code (10 writes versus1 after cancellation) and passes now. Six targeted cases pass with one named Linux-only /proc skip on this Mac. No owner daemon or unrelated process is signalled.

## Session 1 takeover and release candidate

The integration merge `a98ec00` joined `c23411b` and `4e27eb2` with both histories intact.
The shared base was `f6224e2`. The workflow kept both branch triggers. The continuation prompt now
targets this integration branch. This workspace ran Linux rather than the Mac described above.

The merge brought project readiness, coherent provider selection, task reports and history,
conversation context and administration, search hits, keyboard navigation, the frontend casing
regression check, and protection against cancelling a delivered task. The earlier Codex cancellation,
sensitive-file and process-group corrections remain in the merged history.

| Checkpoint | Product change |
|---|---|
| `2fbcfd9` | Prefer the current standard bundle, pick a supported cached model, document isolated launch and rollback, and run scripted Mac acceptance and bundle verification in CI. |
| `31bd1f2` | Start coding tasks from a project, scope approvals to one task, refresh the objective report, and deliver reviewed work through separate release and exact merge approvals. Git commit of the reviewed files stays an explicit operator step. |
| `17367bd` | Read and review project memory, show older tasks when requested, and retain the archived/query view after refresh. The HTTP regression now tests reviewed delivery and durable status. |
| `0644125` | Regenerate the newest answer with the selected model and preserve that choice in history. |
| `77213b2` | Read the task's existing operation ledger during reviewed execution so running and finished work is visible. |
| `ef2d459` | Verify the ad-hoc signature, set macOS 14 as the minimum, and package a 14-day architecture-labelled candidate on integration CI. |
| `5707dc4` | Translate the exact loopback Vite origin for development mutations. Foreign origins and untrusted forwarded metadata still return 403. |
| `e321f4f` | Keep the selected task's project when returning from chat, retain a usable narrow workspace, and require a second step to remove a memory note. |
| `65a7503` | Run the disposable macOS stop-and-resume scenario alongside the delivery scenario and collect both receipts. |

### Verification

- The Linux HTTP suite discovered **466 tests, 462 passed and four skipped**. The desktop passed
  **95 tests across 18 files**, TypeScript and the Vite production build.
- Cloud browser, real loopback development backend and disposable calculator repository.
  Scripted proposals produced failure (exit 1), repair (exit 0), and a completion check.
  Reviewed worktree commit `7a6b046` and merge `2900a8c` belong to the disposable repository.
  The source stayed unchanged until merge. The destination passed the independent calculator
  test, and a new backend process returned `completed`, `merged` and the two test exit codes.
  The test-only preview bridge translated cloud browser request framing for this fixture.
- Additional browser checks covered live ledger progress during a three-second command,
  archived search across refresh, saving an evidence-bound project note, and stop, regeneration
  after stop, regeneration after success, model switching and continuation with scripted chat.
  A 432-pixel browser check kept the task's project and delivery panel visible after switching
  from a personal conversation. Note removal left another note in place. Giving the project
  panels distinct React keys kept one history list and showed only the selected task's approval
  across four switches between two pending tasks.
- Integration run [#115](https://github.com/SamarthRamesha/personal-codex/actions/runs/45425256839)
  passed backend, frontend and macOS, including the scripted full-task demo and native app bundle.
  Run [#114](https://github.com/SamarthRamesha/personal-codex/actions/runs/45423263718) passed the
  earlier startup checkpoint. Run #113 was superseded by #114.
- Run #116 passed all three jobs for `ef2d459`, verified the bundle's ad-hoc signature, and
  published the ARM64 candidate and scripted calculator receipt. [Run #116](https://github.com/SamarthRamesha/personal-codex/actions/runs/45426866817)

Hands-on M3 acceptance, the owner's installed-model run and Developer ID notarization remain
open. The Linux full-task attempt reached the deliberate macOS process-sandbox gate. JARVIS is
offline per the owner. R-36 remains open on `main`.
