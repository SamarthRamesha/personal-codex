#!/bin/sh
# Read-only machine inventory. Does not list/read /DATA contents, change configuration or install anything.
set -u
printf '\n== identity and operating system ==\n'
id
uname -a
if [ -r /etc/os-release ]; then cat /etc/os-release; fi
printf '\n== CPU and instruction sets ==\n'
if command -v lscpu >/dev/null 2>&1; then lscpu; fi
printf '\n== memory and load ==\n'
if command -v free >/dev/null 2>&1; then free -b; fi
uptime
if [ -r /proc/pressure/memory ]; then cat /proc/pressure/memory; fi
printf '\n== storage metadata only; no directory traversal ==\n'
df -PT / /DATA 2>/dev/null
if command -v findmnt >/dev/null 2>&1; then findmnt -T /DATA -o TARGET,SOURCE,FSTYPE,OPTIONS; fi
printf '\n== accelerator devices ==\n'
if command -v lspci >/dev/null 2>&1; then lspci | sed -n '/VGA\|3D controller\|Display controller/p'; fi
if [ -d /dev/dri ]; then ls -l /dev/dri; fi
if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv; fi
printf '\n== available runtimes ==\n'
for item in python3 git docker podman ollama tailscale; do command -v "$item" 2>/dev/null || true; done
python3 --version 2>/dev/null || true
git --version 2>/dev/null || true
printf '\n== containers: names, images and published ports only ==\n'
if command -v docker >/dev/null 2>&1; then
  docker version --format '{{.Server.Version}}' 2>/dev/null || true
  docker info --format 'Architecture={{.Architecture}} CPUs={{.NCPU}} Memory={{.MemTotal}} Driver={{.Driver}}' 2>/dev/null || true
  docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}' 2>/dev/null || true
fi
printf '\n== listeners and interfaces ==\n'
if command -v ss >/dev/null 2>&1; then ss -ltn; fi
if command -v ip >/dev/null 2>&1; then ip -brief address; fi
printf '\n== Tailscale and local inference ==\n'
if command -v tailscale >/dev/null 2>&1; then tailscale version; tailscale ip -4; fi
if command -v ollama >/dev/null 2>&1; then ollama list; fi
if command -v curl >/dev/null 2>&1; then curl --noproxy '*' --connect-timeout 2 --max-time 5 -fsS http://127.0.0.1:11434/api/tags || true; fi
printf '\n== end of read-only inventory ==\n'
