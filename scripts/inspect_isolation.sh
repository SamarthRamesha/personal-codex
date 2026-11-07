#!/bin/sh
# Read-only Linux/runtime metadata. No sudo, installs, app-data contents or service changes.
set -u
printf 'identity\n'; id
printf 'kernel\n'; uname -srm
printf 'namespace-and-cgroup-filesystems\n'
if test -r /proc/filesystems; then sed -n '/cgroup\|overlay\|ext4\|tmpfs/p' /proc/filesystems; fi
printf 'kernel-isolation-status\n'
if test -r /proc/self/status; then sed -n '/^NoNewPrivs:\|^Seccomp:\|^CapBnd:/p' /proc/self/status; fi
for file in /sys/kernel/security/lsm /sys/module/apparmor/parameters/enabled /proc/sys/kernel/unprivileged_userns_clone /proc/sys/user/max_user_namespaces /sys/fs/cgroup/cgroup.controllers; do
  if test -r "$file"; then printf '%s\n' "$file"; head -c 4096 "$file"; printf '\n'; fi
done
printf 'virtualization-device-metadata\n'
if test -e /dev/kvm; then stat -c '%F %U %G %a %n' /dev/kvm; else printf 'KVM device unavailable\n'; fi
printf 'dedicated-layout-and-space\n'
df -Pk /DATA
if command -v findmnt >/dev/null 2>&1; then findmnt -n -o FSTYPE,OPTIONS /DATA; fi
stat -c '%F %u %g %a %n' /DATA/AppData
if test -e /DATA/AppData/PersonalCodex || test -L /DATA/AppData/PersonalCodex; then stat -c '%F %u %g %a %n' /DATA/AppData/PersonalCodex; else printf 'candidate application root absent\n'; fi
printf 'candidate-port-occupancy\n'
if command -v ss >/dev/null 2>&1; then ss -H -ltn | awk '$4 ~ /:(22|443|8787|8443)$/ {print $1,$4}'; fi
printf 'rootless-and-runtime-tools\n'
for executable in docker dockerd-rootless-setuptool.sh newuidmap newgidmap unshare; do command -v "$executable" || true; done
printf 'current-identity-subordinate-maps\n'
identity_name=$(id -un)
for file in /etc/subuid /etc/subgid; do
  if test -r "$file"; then awk -F: -v account="$identity_name" '$1 == account {print FILENAME ":" $0}' "$file"; fi
done
if command -v docker >/dev/null 2>&1; then
  pc_docker() { docker --host unix:///var/run/docker.sock "$@"; }
  printf 'docker-version\n'; pc_docker version --format '{{json .Server}}' 2>/dev/null || printf 'Docker server access unavailable; no privilege workaround\n'
  printf 'docker-isolation-capabilities\n'
  pc_docker info --format 'security={{json .SecurityOptions}} cgroup={{.CgroupVersion}} driver={{.CgroupDriver}} memory={{.MemoryLimit}} swap={{.SwapLimit}} pids={{.PidsLimit}} cpuquota={{.CPUCfsQuota}} storage={{.Driver}}' 2>/dev/null || true
  printf 'tailscale-container-name-and-image-only\n'
  pc_docker ps --filter ancestor=tailscale/tailscale:v1.98.3 --format '{{.Names}} {{.Image}}' 2>/dev/null || true
fi
printf 'Read-only metadata inspection finished. Tailnet policy/certificate/Serve facts need separately authorized existing access.\n'
