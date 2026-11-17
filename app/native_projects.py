"""Local native folder grants. The picker grants exactly one new project root."""
from __future__ import annotations

import hmac
import os
from pathlib import Path
import re
import stat
import subprocess

try:
    import project_files
except ImportError:
    from app import project_files


def allowed(header):
    key = os.getenv("PERSONAL_CODEX_NATIVE_GRANT", "")
    return bool(key and isinstance(header, str) and header.isascii() and hmac.compare_digest(key, header))


def create(request, *, data, source, git="git"):
    if set(request) != {"parent", "name", "device", "inode"}:
        raise ValueError("Unexpected native project fields")
    name = request["name"]
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,59}", name) or name.endswith(" "):
        raise ValueError("Use a project name of up to 60 letters, digits, spaces, hyphens or underscores")
    if not isinstance(request["parent"], str) or not all(type(request[key]) is int for key in ("device", "inode")):
        raise ValueError("Invalid signed folder selection")
    parent = Path(request["parent"])
    if not parent.is_absolute() or parent.resolve(strict=True) != parent:
        raise ValueError("Choose a resolved folder in Finder")
    destination = parent / name
    data = data.resolve()
    default_projects = data / "projects"
    if (data in destination.parents or source in destination.parents) and default_projects not in destination.parents:
        raise ValueError("Choose a project destination outside application source and private data")
    descriptor = os.open(parent, project_files.DIRECTORY)
    try:
        identity = os.fstat(descriptor)
        if (identity.st_dev, identity.st_ino) != (request["device"], request["inode"]):
            raise ValueError("Selected directory changed; choose it again")
        os.mkdir(name, dir_fd=descriptor, mode=0o700)
        child = os.open(name, project_files.DIRECTORY, dir_fd=descriptor)
    finally:
        os.close(descriptor)
    try:
        info = os.fstat(child)
        reopened = destination.stat(follow_symlinks=False)
        if (info.st_dev, info.st_ino) != (reopened.st_dev, reopened.st_ino):
            raise ValueError("New project moved before Git initialization")
        os.mkdir(".git-template", mode=0o700, dir_fd=child)
        try:
            env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(destination),
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "LANG": "C", "LC_ALL": "C"}
            steps = (
                ("init", "--quiet", "--template=.git-template"),
                ("-c", "user.name=Personal Codex", "-c", "user.email=local@personal-codex.invalid",
                 "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "--allow-empty", "-m", "Initialize local project"),
            )
            for args in steps:
                result = subprocess.run([git, *args], cwd=destination, env=env, capture_output=True, timeout=12)
                if result.returncode:
                    raise ValueError("Git initialization failed; the created folder was preserved for inspection")
        finally:
            os.rmdir(".git-template", dir_fd=child)
        return destination, info
    finally:
        os.close(child)


def register(request, *, data, source):
    if set(request) != {"parent", "name", "device", "inode"} or request["name"] != "":
        raise ValueError("Unexpected existing project fields")
    if not isinstance(request["parent"], str) or not all(type(request[key]) is int for key in ("device", "inode")):
        raise ValueError("Invalid signed folder selection")
    root = Path(request["parent"])
    data = data.resolve()
    if (not root.is_absolute() or root.resolve(strict=True) != root or root in {data, source} or root in source.parents
            or ((data in root.parents or source in root.parents) and data / "projects" not in root.parents)):
        raise ValueError("Choose a specific Git project outside application source and private data")
    fd = os.open(root, project_files.DIRECTORY)
    try:
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != (request["device"], request["inode"]):
            raise ValueError("Selected repository changed; choose it again")
        directory = os.stat(".git", dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISDIR(directory.st_mode):
            raise ValueError("Choose the root of an existing Git repository")
        return root, info
    finally:
        os.close(fd)


def authorized(store, path):
    row = store.one("SELECT device, inode FROM native_project_roots WHERE path=?", (str(path),))
    if not row:
        return False
    info = path.stat(follow_symlinks=False)
    return (stat.S_ISDIR(info.st_mode) and not path.is_symlink()
            and (info.st_dev, info.st_ino) == (row["device"], row["inode"]))
