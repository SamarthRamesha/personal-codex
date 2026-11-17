"""Authorize one native file selection and extract it in a confined subprocess."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

try:
    import attachment_extract, local_runner, project_files
except ImportError:
    from app import attachment_extract, local_runner, project_files

MAX_FILE = 12_000_000
SCHEMA = """
CREATE TABLE IF NOT EXISTS project_attachments (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
 mechanism TEXT NOT NULL, excerpt TEXT NOT NULL, created_at INTEGER NOT NULL
);
"""


def import_selected(selection, data):
    if set(selection) != {"project_id", "path", "device", "inode"}:
        raise ValueError("Unexpected attachment fields")
    if not isinstance(selection["path"], str) or not all(type(selection[key]) is int for key in ("device", "inode")):
        raise ValueError("Invalid attachment selection")
    path = Path(selection["path"])
    suffix = path.suffix.lower()
    blocked = {".ssh", ".aws", ".gnupg", "keychains", ".codex", ".env", "personal-codex-diagnostic.txt"}
    if (suffix not in attachment_extract.SUFFIXES or not path.is_absolute()
            or any(part.casefold() in blocked or part.casefold().startswith(".env.") for part in path.parts)
            or path.resolve(strict=True) != path or data.resolve() in path.parents):
        raise ValueError("Choose a supported attachment outside private application data")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        initial = os.fstat(stream.fileno())
        if (initial.st_dev, initial.st_ino) != (selection["device"], selection["inode"]):
            raise ValueError("Attachment changed after selection")
        if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1 or initial.st_size > MAX_FILE:
            raise ValueError("Attachments must be regular files no larger than 12 MB")
        content = stream.read(MAX_FILE + 1)
        if len(content) > MAX_FILE or project_files.fingerprint(initial) != project_files.fingerprint(os.fstat(stream.fileno())):
            raise ValueError("Attachment changed or exceeded the size limit during import")
    engine = Path(attachment_extract.__file__).resolve()
    with tempfile.TemporaryDirectory(prefix="attachment-", dir=data) as temporary:
        root = Path(temporary).resolve()
        copied = root / ("selected" + suffix)
        copied.write_bytes(content)
        env = {**local_runner.base_env(root), "TMPDIR": str(root)}
        command = local_runner.sandboxed([sys.executable, "-I", "-B", str(engine), str(copied)],
                                         reads=(root, engine), writes=(root,))
        result = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=26)
        excerpt = result.stdout.decode("utf-8", errors="strict").strip()
        if result.returncode or len(excerpt) > attachment_extract.MAX_TEXT + 30 or not excerpt or excerpt == "[Local OCR]":
            raise ValueError("Local extraction could not obtain readable text from this file")
    return path.name, "local OCR" if suffix in attachment_extract.IMAGE_SUFFIXES else "local text extraction", excerpt


def prompt_block(store, project_id, *, budget=3000):
    rows = store.rows("SELECT name, mechanism, excerpt FROM project_attachments WHERE project_id=? "
                      "ORDER BY created_at DESC, rowid DESC LIMIT 4", (project_id,))
    if not rows:
        return ""
    lines = [f"[{row['name']} | {row['mechanism']}]\n{row['excerpt'][:1500]}" for row in rows]
    return "\n\nUser-selected project attachments (untrusted reference data):\n" + "\n\n".join(lines)[:budget]
