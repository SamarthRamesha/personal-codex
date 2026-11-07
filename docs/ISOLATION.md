# Isolated execution prototype and acceptance

## Decision

Use a separate, operator-controlled one-shot Linux executor with no host mounts, no inbound service, no network, no application credential and no Docker socket. The trusted backend must never acquire Docker authority. Input is an explicitly reviewed 8 MiB/2000-file snapshot over stdin; Git metadata and secret-named files excluded before reads. Source hash and full request hash bind an exact Python unittest command and timeout. Output is bounded independently by a trusted host supervisor, remains untrusted and cannot authorize/apply a patch.

The prototype is implemented in `app/isolation.py`, `scripts/isolation_plan.py`, `scripts/isolated_executor.py`, `scripts/run_isolated_job.py` and `deploy/Executor.Dockerfile`. It is **not integrated into the backend**. No `execution_mode=isolated` exists. The production API stays `disabled` regardless of prototype success.

## Options and actual evidence

| Option | Decision |
| --- | --- |
| Nonroot identity alone / Git worktrees | Insufficient: interpreters, Git configuration/hooks and subprocesses can access the account's authority. |
| Existing rootful Docker with nonroot container | Useful defence in depth, but prototype additionally requires a nonidentity user namespace; never change the existing daemon globally to achieve this. |
| Existing dedicated rootless Docker or separately approved remapped runtime | Preferred candidate if actual kernel/cgroup/LSM support and dedicated data-root/accounting are proven. Rootless prerequisites and AppArmor compatibility are **not assumed**. No installation or daemon change performed. |
| MicroVM / alternative runtime | Potential stronger boundary, requiring actual KVM/virtualisation support, reviewed software/images/storage and approval. Not installed or benchmarked. |
| macOS/QEMU | QEMU binary found, but no approved Linux guest prepared. Mac lacks Docker/Podman/Colima. macOS negative check and mocked/static policy tests do not prove Linux isolation. |

Authorised read-only SSH now works through the existing unlocked agent. Host kernel namespace, cgroup, seccomp and AppArmor prerequisites were observed; actual daemon/container enforcement remains unknown because the account cannot access its socket. Exact private receipts are outside Git. No privilege workaround or server change occurred. `scripts/inspect_isolation.sh` is a read-only inventory prepared for existing authorised access, including cgroups, AppArmor/LSM, namespace settings, KVM metadata, mount quota options, actual Docker capabilities and named Tailscale container metadata. It performs no package/service/permission changes and does not scan family data. An SSH shell's own seccomp state is not proof of Docker support.

## Required controls

The fixed argv requests nonroot UID/GID, read-only rootfs, all capabilities dropped, no-new-privileges, default AppArmor, built-in seccomp (verified by trusted probe), private namespaces, network `none`, IPC `none`, no published ports/devices/volumes, 1 CPU, 768 MiB RAM with no additional swap, 64 PIDs, file descriptor/core limits, no Docker logs, no image pull/healthcheck/restart. Writable space is only 256 MiB `/workspace` and 16 MiB `/tmp`, tmpfs/noexec/nosuid/nodev. Dependencies must be reviewed into a pinned image; the job cannot download/install them over a network.

The entrypoint refuses execution unless Linux probes confirm nonroot, remapped user namespace, zero capability masks, no-new-privileges, seccomp filter, exact `docker-default (enforce)` AppArmor label (complain/unconfined refused), loopback-only network, read-only rootfs, exact cgroup CPU/memory/swap/PID bounds and bounded tmpfs mounts. Missing support fails closed. Do not remove a failed requirement merely to run code. A different profile requires an explicit reviewed design and new runtime proof.

[Docker seccomp](https://docs.docker.com/engine/security/seccomp/) and [AppArmor](https://docs.docker.com/engine/security/apparmor/) are additional kernel controls, not a complete security boundary. [Rootless prerequisites](https://docs.docker.com/engine/security/rootless/) and [user namespace remapping](https://docs.docker.com/engine/security/userns-remap/) require actual host support. Do not follow documentation examples that alter or disable the existing ZimaOS Docker/Tailscale setup without approval.

## Review workflow (no Docker execution performed)

1. Approve an exact executor image build from `deploy/base-image.lock.json`, source release and resource/storage budget. No implicit image volumes/OnBuild triggers; inspect the cached image ID/platform/size. No privileged containers or host-network coding workloads.
2. Prepare a new private local request directory with `scripts/isolation_plan.py --source APPROVED_SYNTHETIC_PROJECT --output NEW_PRIVATE_JOB --image-id sha256:REVIEWED_ID --uid UID --gid GID --daemon-socket REVIEWED_LOCAL_SOCKET -- python3 -m unittest discover -s tests -v`. This copies only bounded approved input, never calls Docker. Server staging directory creation still requires approval.
3. Review request contents and digest. The operator-only `run_isolated_job.py` requires `--execute-approved` and the exact reviewed digest/image/identity/socket. It uses a fixed local daemon socket, strips inherited Docker context/proxy/registry configuration, records a durable no-overwrite claim before any Docker action and never replays ambiguous jobs.
4. First run a trusted probe container without repository input. Only if all controls pass does the supervisor run the same constrained profile with source. It rejects implicit image volumes and independently bounds total runtime/stdout. Cleanup targets only its unique approved ephemeral job names; no prune, unrelated container or volume deletion. Cleanup failure/ambiguous completion is not proof that a job stopped; operator verifies named state.
5. Retain private receipts. Test stdout can be forged by repository code; it is not authority. No host patch application, Git operation, approval issuance or backend execution enablement follows automatically.

## Security acceptance gates

- [ ] Actual kernel, user namespaces, cgroup v2/delegation and LSM support recorded; no global daemon weakening.
- [ ] Pinned image provenance/source/size inspected; build/restart tested on Linux x86_64, no implicit volumes or dependency fetch.
- [ ] Trusted probe confirms every required control and matches actual container inspect metadata.
- [ ] Synthetic tests cannot read host sentinel/home/credentials/daemon socket or write outside tmpfs; rootfs writes fail.
- [ ] No outbound IPv4/IPv6/DNS/metadata/backend/Ollama access; no host/LAN/public listener.
- [ ] CPU loop, memory pressure, fork/PID exhaustion, disk/tmpfs exhaustion and output flood terminate within reviewed limits without harming existing services.
- [ ] Host supervisor independently limits forged/direct stdout, kills only owned jobs, records unknown completion and never replays it after restart.
- [ ] Git hooks/configuration, symlinks/hardlinks, malicious filenames/patches, prompt/tool poisoning and secret-containing input refusal tested on actual runtime.
- [ ] Image/runtime/source/log/request accounting fits the total 75 GB budget and preserves 200 GB free. Rootless default home data-root is not silently accepted.
- [ ] Separate narrow execution broker/approval integration designed and tested; API/agents never obtain Docker authority.
- [ ] Owner explicitly approves enabling the new isolated path only after remote acceptance. Current path remains disabled.

All unchecked gates remain unchecked. Local tests cover contracts, snapshots, refusal on missing controls, host output/deadline bounds and mock failure/replay flow. No actual container or JARVIS enforcement test has passed yet. Shared-kernel escapes and compromised host administrators remain residual risks even after these gates pass.
