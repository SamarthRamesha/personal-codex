# Encrypted checkpoint and disaster recovery

`app/recovery.py` and `scripts/recovery_bundle.py` implement an **offline**, authenticated-encrypted, new-destination-only recovery envelope. This complements the existing online SQLite snapshots. The operator tool uses optional `cryptography==49.0.0`, already available on this Mac; the backend remains standard-library-only. No JARVIS package was installed. Target tool/dependency installation or a larger streaming backup system requires approval.

## Included and excluded

Included: coherent stopped-backend SQLite snapshot (conversations, messages, tasks, approvals, memory, execution state and ledger), full regular files in dedicated `data/projects` and `data/workspaces` including standalone Git repositories, an explicitly supplied source release zip, and only the five nonsecret reviewed deployment settings.

Excluded without collection: credential directories, SSH/private keys outside that dedicated scope, owner/worker tokens, models/images, existing backup directories, unrelated project paths and native credential storage. Do not place encryption keys inside data/backups. Native stores only its endpoint preference; reconnect explicitly after restoring and rotating credentials. Images are rebuilt/restored separately from reviewed release/digest metadata; no hidden image download occurs.

The backend must be stopped: its existing instance flock prevents concurrent checkpointing. Other repository writers must also be quiescent; per-file identity/change checks cannot make an arbitrary externally edited multi-file tree atomic. Symlinks, hardlink aliases, special files, protected diagnostic paths and known broad/family/other-app roots fail closed. No Git command, hook, filter or configuration include executes while collecting data.

## Encryption and limits

[Fernet](https://cryptography.io/en/latest/fernet/) provides authenticated encryption through the reviewed library. The independent private 0600 key stays outside application data and the bundle. No key value is printed, transmitted or stored in the archive. Tar/SQLite snapshot data is assembled in bounded memory; no plaintext staging archive is written. Encryption does not erase original plaintext database pages or prior SQLite snapshots.

The complete plaintext envelope is capped at **64 MiB**, including tar overhead, and file counts are bounded. A larger database/project fails rather than producing a partial successful backup. This is an intentional initial operator-tool limit, **not full-capacity disaster recovery for a 75 GB installation**. Before exceeding it, approve/test a vetted streaming/encrypted backup system and off-device capacity/retention; do not invent a streaming cryptographic format or silently omit dependencies/files. Timestamp and approximate size remain visible; encryption key loss prevents recovery and compromise permits forged bundles.

## Prepared commands, never against personal/server data in this run

```sh
# Backend and other writers must be stopped; server stop/write actions require approval.
python3 scripts/recovery_bundle.py checkpoint --data APPROVED_DATA --output NEW_ENCRYPTED_BUNDLE --key-file SEPARATE_PRIVATE_KEY --release-zip REVIEWED_SOURCE_ZIP --review-env PRIVATE_LITERAL_SETTINGS
python3 scripts/recovery_bundle.py restore --bundle ENCRYPTED_BUNDLE --new-root COMPLETELY_NEW_PRIVATE_ROOT --key-file SEPARATE_PRIVATE_KEY
```

The key is an independent Fernet key under explicit operator custody, never the SSH key or owner/worker token. Its generation, escrow and authorised target installation must be reviewed. Never paste key material into chat or command arguments. Do not overwrite, auto-delete or automatically age out backups. Retention/off-device destinations/scheduling remain approval-gated.

## Restore behavior

Authenticate and validate archive inventory, hashes, canonical paths, entry types, limits, SQLite integrity and dedicated path references before creating output. Write only to a wholly new private root. Database project/workspace paths relocate; pending/approved approvals become revoked, active operations/jobs/messages interrupted, worker presence reset and ready workspaces marked recovery-review. Completed ledger evidence is preserved. No model, patch or test is replayed.

A recovery lock is written before any restored payload; completion receipt is written last. Startup refuses an incomplete recovery even with execution disabled, and refuses development execution for a completed recovery. Source release remains a zip for operator review. Configuration is a review JSON, never automatically applied. Worktree absolute Git pointers, includes/alternates and external configuration need isolated repair/review; no automatic `git worktree repair` executes on the host. Regenerate owner/worker credentials, reconnect native/worker, verify private HTTPS, then run a fresh synthetic acceptance test before an approved service switch. Retain original release/database/bundle for rollback.

## Evidence and recovery objectives

Local synthetic unit tests cover encryption roundtrip, actual standalone Git history, DB/ledger preservation, relocation, wrong key/tamper, links/traversal/duplicate archive entries, budgets, active-lock refusal, no overwrite, excluded credentials/backups, stale approval revocation and partial-restore startup refusal. A separate drill verifies records before the checkpoint return, later records do not, and original later data remains intact.

Measured tiny warm Mac fixture: checkpoint **9 ms**, restore **10 ms**, six drill checks passed. This is not a JARVIS RTO estimate. Recovery point is only the latest completed manual checkpoint; no continuous backup or automatic schedule exists. Real recovery time also includes approved infrastructure/image restoration, separate key access, credentials, Git review and native reconnection. Actual JARVIS RTO/RPO/off-device restore and larger-data recovery are unverified deployment gates.
