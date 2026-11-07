# Installation review after read-only inspection

No installation is authorised. This document records the updated deployment contract; exact host/account/service metadata and commands remain in the private approval package outside Git.

## Storage path and identity

The earlier application-parent candidate did not satisfy ancestor safety. The default review path is now `/DATA/PersonalCodex`, under the protected persistent data parent. This is a **new proposal requiring approval**, not a directory creation or migration. No parent permission, ownership, mount, inode flag or existing application directory was changed.

Preflight rejects symlinks, untrusted ancestor owners and writable non-sticky ancestors before reading credential files. A private leaf directory alone does not protect its name from a writer of its parent; see [Linux rename permission rules](https://man7.org/linux/man-pages/man2/rename.2.html). Sticky shared ancestors are accepted only with trusted owners and a subsequently verified private owned layout. No automatic exception is granted for the old path.

Use a separately reviewed numeric nonroot UID/GID, not a broad host-user identity by accident. An unused numeric candidate was identified but is not reserved or applied. The Docker daemon's actual user-namespace mapping must be checked before assigning host ownership. No account creation or Docker-group addition is proposed. Existing service configuration, family storage and shared parent permissions remain untouched.

## Current access distinction

Read-only SSH now works through the user's existing unlocked agent. It does not confer Docker daemon authority. The current account cannot access the daemon socket; no sudo, group/ACL change, API workaround or alternative privileged shell was attempted. A running service/client binary is not a successful daemon interrogation. Capability fields from a failed query are **unknown**, never false proof that a kernel feature is absent.

The read-only inventory now avoids the inaccessible user registry configuration, queries only the explicit local daemon and emits capability values only after a successful server response. Compose/Python availability has been checked separately; no host package installation is needed for the API plan. Recovery dependency compatibility/security remains a separate review item; an existing version is not an installation or acceptance certificate.

The host kernel reports relevant namespace/seccomp/LSM/cgroup capabilities. This is not evidence that the proposed Docker container enforces them. Rootless prerequisites were not found in the inspected PATH. Actual userns mapping, seccomp/AppArmor profile, cgroup limits, image size/mounts, and existing Serve configuration still need an already-authorised Docker operator's scoped read-only receipt.

No host listener was reported on the candidate backend ports. Private DNS resolves correctly; verified TLS connection to private443 was refused. Neither observation proves the existing Serve configuration is empty: a userspace tailnet service need not appear as a host listening socket. Never replace a Serve handler without its actual status/configuration review.

## Deterministic API build input

`scripts/prepare_build_context.py` reads only the trusted release's committed Git objects, never the working tree, untracked diagnostic/data or agent repositories. It creates a deterministic minimal tar.gz with root `Dockerfile`, direct `app/*.py`, three web assets and the restore helper. Timestamps/owners/order are normalised; per-file SHA256, exact source commit, context hash and pinned official base reference are recorded.

```sh
python3 scripts/prepare_build_context.py --repository TRUSTED_RELEASE_REPOSITORY --commit REVIEWED_COMMIT --output NEW_CONTEXT.tar.gz --manifest NEW_CONTEXT.json
```

Preparation invokes no Docker, download, build or publication. Identical committed inputs produce identical context bytes; this does not certify byte-identical image builds, signatures or vulnerability status. Never point the helper at an untrusted agent repository.

After **explicit download/build approval**, an already-authorised Docker operator can build from this reviewed minimal stdin context without unpacking a broad working tree:

```sh
# MUTATION — approval, current capacity and pinned-source review required first.
docker --host unix:///var/run/docker.sock build --platform linux/amd64 --network none --build-arg PYTHON_IMAGE=REVIEWED_PINNED_REFERENCE --label org.opencontainers.image.revision=REVIEWED_COMMIT --tag personal-codex:REVIEWED_COMMIT - < REVIEWED_CONTEXT.tar.gz
```

The base image may be fetched during this approved action if absent. No apt/pip or networked build RUN is defined. Record the resulting local image ID/platform/size/provenance; `PC_IMAGE` remains unresolved until that build/inspection. Do not start a service merely because a context exists or Compose configuration parses.

## Approval sequence

1. Obtain scoped daemon/Serve metadata from an existing authorised operator. Do not broaden the SSH account's privileges. Obtain the complete current tailnet policy/family/admin requirements separately.
2. Review protected root, numeric identity/mapping, source/context hashes, image download/build size, storage and recovery suballocations. Full encrypted recovery still has a64MiB envelope limit; larger capacity needs reviewed streaming recovery.
3. Approve creation of only the exact new private application layout and bounded image build. No recursive ownership changes or existing app modification.
4. After successful protected-parent/layout/image preflight, approve the execution-disabled API service. Verify actual loopback bind, auth, resource limits, persistence/recovery, logs and existing service health.
5. Approve a conflict-free change to the verified existing Serve container and reviewed full ACL policy. No reset/Funnel/public listener or TLS bypass.
6. After real remote acceptance, separately approve persistent outbound Mac worker and any future isolated execution runtime/broker. Production coding stays disabled until actual containment and integration pass.
7. GitHub publication is separate and remains unapproved.

The private review package includes precise known values, unresolved fields, read-only operator checklist and phased mutation commands for later approval. No infrastructure action was performed while producing it.
