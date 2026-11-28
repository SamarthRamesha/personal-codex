"""Constrained macOS subprocesses for a user-authorized local agent run.

The profile confines file data, writes, and network traffic. Command output,
timeouts, and resource caps are handled by the caller. Startup fails if the
process-only sandbox is unavailable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

SANDBOX = "/usr/bin/sandbox-exec"
SYSTEM_READS = (
    "/System/Library", "/bin", "/usr/bin", "/usr/lib", "/usr/share", "/Library/Developer/CommandLineTools",
    "/private/var/db/dyld", "/private/var/db/timezone", "/opt/homebrew/Cellar",
    "/opt/homebrew/opt", "/opt/homebrew/share", "/opt/homebrew/lib/node_modules/npm",
)
SYSTEM_DIRECTORIES = ("/", "/private", "/usr", "/System", "/System/Volumes", "/dev", "/Library", "/etc", "/var")
SYSTEM_FILES = ("/dev/null", "/dev/urandom", "/dev/random", "/private/etc/localtime", "/opt/homebrew/etc/openssl@4/openssl.cnf",
                "/opt/homebrew/etc/openssl@3/openssl.cnf")


def trusted_program(name):
    location = shutil.which(name)
    if not location:
        raise ValueError(f"Required local program is missing: {name}")
    return Path(location).resolve()


def matcher(label, path):
    return f"({label} {json.dumps(str(path), ensure_ascii=False)})"


def profile(read_roots, write_roots, programs):
    roots = [*SYSTEM_READS, *read_roots]
    for program in programs:
        p = Path(program).resolve()
        # Tool launch paths may be outside Homebrew (for example setup-node's cache).
        # Permit the selected executable and npm's own module tree, never its broad parent.
        roots.append(p)
        if p.name == "npm-cli.js" and p.parent.name == "bin" and p.parent.parent.name == "npm":
            roots.append(p.parent.parent)
        for parent in p.parents:
            if parent.name == "Python.framework":
                roots.append(parent)
                break
        if "bin" == p.parent.name and ".nvm" in p.parts:
            roots.append(p.parent.parent)

    # The vnode filter avoids denying anonymous runtime reads, which macOS
    # represents as file-read-data with no ordinary filesystem object.
    readable = " ".join([*(matcher("subpath", root) for root in roots),
                         *(matcher("literal", file) for file in SYSTEM_FILES)])
    directories = " ".join(matcher("literal", path) for path in SYSTEM_DIRECTORIES)
    writable = " ".join([*(matcher("subpath", root) for root in write_roots),
                          matcher("literal", "/dev/null")])
    return (
        "(version 1) (allow default) (deny network*) (deny mach-lookup) (deny process-info* (require-not (target self))) (deny signal) "
        "(deny file-read-data (require-all "
        "(require-any (vnode-type REGULAR-FILE) (vnode-type SYMLINK)) "
        f"(require-not (require-any {readable})))) "
        "(deny file-read-data (require-all (vnode-type DIRECTORY) "
        f"(require-not (require-any {readable} {directories})))) "
        f"(deny file-write* (require-not (require-any {writable}))) "
        "(deny file-read-data (subpath \"/System/Volumes/Data\")) "
    )


def sandboxed(argv, *, reads, writes, programs=()):
    if platform.system() != "Darwin" or not os.path.isfile(SANDBOX):
        raise ValueError("The autonomous runner requires the verified macOS process sandbox")
    executable = trusted_program(argv[0])
    return [SANDBOX, "-p", profile(reads, writes, (executable, *programs)), str(executable), *argv[1:]]


def validate_command(argv):
    pairs = (["python3", "-m", "unittest"], ["python", "-m", "unittest"],
             ["python3", "-m", "pytest"], ["python", "-m", "pytest"])
    allowed = (argv[:3] in pairs or argv[0] == "pytest"
               or argv in (["npm", "test"], ["npm", "run", "build"], ["npm", "run", "lint"], ["npm", "run", "typecheck"]))
    if not allowed:
        raise ValueError("Use an exact unittest, pytest, npm test, build, lint or typecheck command")


def base_env(workspace):
    return {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(workspace), "PWD": str(workspace),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "PYTHONDONTWRITEBYTECODE": "1", "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}


def create_worktree(root, target, branch):
    if not (root / ".git").is_dir() or (root / ".git").is_symlink():
        raise ValueError("An ordinary Git checkout with a real .git directory is required")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.mkdir(mode=0o700)
    git = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
           "-c", "protocol.allow=never", "-C", str(root), "worktree", "add", "-b", branch, str(target)]
    argv = sandboxed(git, reads=(root, target), writes=(root / ".git", target))
    with subprocess.Popen(argv, cwd=target, env=base_env(target), stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, start_new_session=True) as process:
        try:
            if process.wait(timeout=35):
                raise ValueError("Sandboxed Git could not create the worktree. The original project files were preserved.")
        except subprocess.TimeoutExpired:
            process.kill()
            raise ValueError("Sandboxed Git worktree setup timed out") from None


def verify_boundary(workspace, external_fixture, python, *, node=None):
    """Prove selected denial cases without accessing real unrelated files."""
    argv = [python, "-I", "-B", "-c", """
import os, socket, sys
from pathlib import Path
root, outside = map(Path, sys.argv[1:])
assert root.joinpath('visible.txt').read_text() == 'workspace'
root.joinpath('wrote.txt').write_text('checked')
for operation in (lambda: outside.read_text(), lambda: list(outside.parent.iterdir()),
                  lambda: outside.write_text('unexpected'), lambda: (root/'alias.txt').read_text()):
    try:
        operation()
    except PermissionError:
        continue
    raise AssertionError('Unexpected workspace-external access')
for family, address in ((socket.AF_INET, ('127.0.0.1', 1)), (socket.AF_INET6, ('::1', 1))):
    try:
        with socket.socket(family, socket.SOCK_STREAM) as connection:
            connection.connect(address)
    except PermissionError:
        continue
    raise AssertionError('Unexpected network access')
print('process sandbox verified')
""", str(workspace), str(external_fixture)]
    return subprocess.run(sandboxed(argv, reads=(workspace,), writes=(workspace,), programs=(node,) if node else ()),
                          cwd=workspace, env=base_env(workspace), capture_output=True, text=True, timeout=15)
