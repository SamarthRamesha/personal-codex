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
