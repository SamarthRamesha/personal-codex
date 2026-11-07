# Mission 1B local release summary

Starting source: `6c0c10105b39e2e667c547b883693a12c89196bd`, branch `personal-codex/stabilization`. Subsequent security-engineering commits are local only. No GitHub publication/PR/push is authorised. Exact final tip and tests are recorded in the handoff and private report.

This milestone adds durable Mac no-replay claims and credential rotation; strict worker schemas and monotonic/chunk limits; descriptor snapshots and authenticated encrypted multi-component recovery; stale-authority revocation and locked restore; production write admission and SQLite page cap; a separate operator-only no-host-mount/no-network executor prototype and supervisor; pinned public image metadata; and read-only runtime/HTTPS acceptance tooling.

Backend Docker image remains stdlib-only. Recovery cryptography is optional operator tooling, not a runtime dependency. Worker service arguments now require an existing private `--state-dir`; templates updated. The initial backend additionally requires enabled storage admission. Credential mount is a dedicated read-only directory containing exactly owner/worker token files to support atomic rotation.

No backend isolated execution mode or Docker authority was added. Linux enforcement, actual image builds/containers, remote inference/native HTTPS, complete family-aware ACL policy and target recovery/storage are unverified. Full recovery envelope is capped at 64 MiB; no blanket production certification or complete Mission 1 claim. Existing diagnostic, private notes, credentials, databases, fixtures and dependencies are excluded from Git/source releases. Pinned metadata does not mean an image was pulled, signature checked or built reproducibly.

Before publishing, review the exact staged diff/source archive and obtain explicit GitHub approval. Before installation, resolve read-only access and actual runtime/policy facts, then obtain scoped infrastructure approval. Do not apply templates or enable coding automatically.
