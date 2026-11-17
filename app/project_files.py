"""Descriptor-relative access to text files in a Personal Codex workspace."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import PurePosixPath
import secrets
import stat

LIMIT = 2_000_000
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


@contextmanager
def parent_directory(root, relative, *, create=False):
    path = PurePosixPath(relative)
    parts = relative.split("/")
    if (path.is_absolute() or len(parts) > 12 or "\\" in relative
            or any(part in ("", ".", "..") for part in parts)
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in relative)):
        raise ValueError("File path must use canonical relative components")
    current = os.open(root, DIRECTORY)
    try:
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=current)
                except FileExistsError:
                    pass
            child = os.open(part, DIRECTORY, dir_fd=current)
            os.close(current)
            current = child
        yield current, parts[-1]
    finally:
        os.close(current)


def snapshot(parent, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, "rb") as stream:
        initial = os.fstat(stream.fileno())
        if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:
            raise ValueError("Workspace file must be a regular file with a single link")
        if initial.st_size > LIMIT:
            raise ValueError("Workspace text file exceeds the 2 MB size limit")
        data = stream.read(LIMIT + 1)
        current = os.fstat(stream.fileno())
        if len(data) > LIMIT or fingerprint(initial) != fingerprint(current):
            raise ValueError("Workspace file changed while being read")
        return data, current


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text_file(root, relative):
    with parent_directory(root, relative) as (parent, name):
        raw, _ = snapshot(parent, name)
    if b"\x00" in raw:
        raise ValueError("Binary file cannot be edited as text")
    try:
        return raw, raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Workspace file is not UTF-8 text") from None


def write_file(root, relative, content, *, expected=None, make_parents=False):
    """Publish a fully written file. New files are installed without replacement."""
    if len(content) > LIMIT or b"\x00" in content:
        raise ValueError("Generated UTF-8 text exceeds the file limit or contains NUL")
    with parent_directory(root, relative, create=make_parents) as (parent, name):
        mode = 0o600
        if expected is not None:
            before, info = snapshot(parent, name)
            if digest(before) != expected:
                raise ValueError("File changed after review; request a new proposal and approval")
            mode = stat.S_IMODE(info.st_mode) & 0o777
        temp = ".codex-write-" + secrets.token_hex(12)
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), mode)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if expected is None:
                os.link(temp, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            else:
                latest = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if fingerprint(info) != fingerprint(latest):
                    raise ValueError("File changed immediately before the update")
                os.replace(temp, name, src_dir_fd=parent, dst_dir_fd=parent)
        finally:
            try:
                os.unlink(temp, dir_fd=parent)
            except FileNotFoundError:
                pass
    return {"path": relative, "sha256_before": expected, "sha256_after": digest(content), "bytes_after": len(content)}
