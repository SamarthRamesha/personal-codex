# Disposable Linux container verification

Updated 20 November 2026. This evidence is from a separate disposable test machine, **not JARVIS**.

## Current accepted API

- Source: `282b90d759c2cf76e3306fe87ee6a1f74f7922f2`.
- Minimal committed context SHA256: `f440733284af9f5da02f2d3e5a7275e7fddd719120c1936ffde41eeb97bd89e6`.
- Local test image ID: `sha256:6e93d5296b60fd6eec7e781391b57590c4a147e0db87c84dba8d0e66b134bd0f`.
- Seventeen actual assertions passed in 42.435 seconds; idle 21.46 MiB/one process; final container exit 0 / no OOM.
- Current desktop/docs/launcher changes leave the API context bytes identical. Source-context generation reads committed Git objects only, excluding diagnostics, credentials, runtime data and untracked files.

## Actual checks

1. Build from the exact context with build networking disabled and an already cached pinned official Python base.
2. Authenticated startup/readiness/storage behavior; missing owner rejected; worker cannot exercise owner authority.
3. Worker-only/no-cloud-fallback and disabled execution; direct provider registration and repository execution refused.
4. Exact synthetic private-proxy authority and active additive API no-connect filter.
5. Effective numeric nonroot identity, read-only root, dropALL, no-new-privileges and actual 1 CPU / 512 MiB / no additional swap / 128 PID bounds.
6. PID 1 zero effective capabilities and two seccomp filters; only dedicated data and read-only token mounts.
7. Conversation persistence across a clean restart.
8. Actual pinned-image FTS5 availability, explicit selected-excerpt indexing/hash attribution and removal of later hits.
9. Exact proposal-cycle detection and the content-progress boundary in the built image.

The seventeen assertions group related conditions above; the private receipt retains each individual name and measured values. No image was published or transferred to JARVIS.

## Limits

The Debian 13 x86_64 guest used 1 vCPU / 1536 MiB RAM / an 8 GiB overlay, no host mounts and loopback-only SSH forwarding. Its independently created operator has authority only in this disposable machine. The original firmware-stalled overlay, successful overlay and restart snapshots are preserved privately.

The small test fixture uses 1 GB free reserve / 5 GB data admission. Production settings remain 200 GB free reserve / 24 GB initial data admission; no production capacity is inferred. An identity UID map was observed, not a remapped user namespace. This does not certify an isolated coding executor. Docker healthcheck/exec processes are outside the API process's additional syscall filter.

JARVIS storage, image loading, mapped identity, Compose/importer field retention, runtime constraints, real HTTPS/Serve/access policy, family preservation and backup scale all remain unverified. Production coding remains disabled. Read [deployment](../DEPLOYMENT.md).

Earlier 13-check and 16-check source-specific receipts remain in private history. They must not be represented as containing later code. Later changes to API build inputs require fresh acceptance or demonstrated byte equivalence; desktop-only changes do not automatically invalidate identical API bytes.
