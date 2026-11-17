"""Review validated task changes and copy approved additions into a new repository."""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
import subprocess

try:
    import local_runner, project_files, tools
except ImportError:
    from app import local_runner, project_files, tools


def git_read(source, worktree, arguments):
    root = worktree or source
    argv = ["git", "--no-pager", "-c", "core.fsmonitor=false", "-c", "protocol.allow=never",
            "-C", str(root), *arguments]
    command = local_runner.sandboxed(argv, reads=(source, root), writes=())
    return subprocess.run(command, cwd=root, env=local_runner.base_env(root), capture_output=True, timeout=12)


def review(run, source, worktree, allow_publish):
    expected = {}
    for item in run["evidence"]:
        expected.update(item.get("hashes", {}))
    if not expected or len(expected) > 120:
        raise ValueError("No bounded set of validated file changes is available")
    files, contents = [], {}
    digest = hashlib.sha256()
    digest.update(str(source).encode())
    digest.update(b"\x00")
    head = git_read(source, worktree, ["rev-parse", "HEAD"])
    if head.returncode:
        raise ValueError("Cannot read the source revision for this task worktree")
    digest.update(head.stdout)
    baseline = head.stdout.decode("ascii").strip()
    total = 0
    for relative, expected_hash in sorted(expected.items()):
        tools.resolve_in_workspace(worktree, relative)
        raw, current = project_files.text_file(worktree, relative)
        if project_files.digest(raw) != expected_hash:
            raise ValueError("A task file changed after validation. Revalidate before applying changes.")
        total += len(raw)
        if total > 500_000:
            raise ValueError("Task changes exceed the review byte budget")
        contents[relative] = raw
        digest.update(json.dumps([relative, expected_hash], ensure_ascii=False).encode())
        entry = git_read(source, worktree, ["ls-tree", "-z", "HEAD", "--", relative])
        if entry.returncode:
            raise ValueError("Cannot verify a task file against the initial Git revision")
        initial = ""
        initial_hash = None
        if entry.stdout:
            if not entry.stdout.startswith((b"100644 blob ", b"100755 blob ")):
                raise ValueError("Only ordinary tracked files are eligible for review")
            allow_publish = False
            original = git_read(source, worktree, ["show", f"HEAD:{relative}"])
            if original.returncode or len(original.stdout) > project_files.LIMIT:
                raise ValueError("Cannot display the initial file version")
            initial = original.stdout.decode("utf-8")
            initial_hash = project_files.digest(original.stdout)
        delta = list(difflib.unified_diff(initial.splitlines(), current.splitlines(),
                                          fromfile=f"a/{relative}" if entry.stdout else "/dev/null",
                                          tofile=f"b/{relative}", n=2, lineterm=""))
        files.append({"path": relative, "new": not entry.stdout, "before": initial_hash, "diff": delta[:400], "truncated": len(delta) > 400})
    if sum(len(line) for file in files for line in file["diff"]) > 400_000:
        raise ValueError("Changeset is too large for review")
    return {"digest": digest.hexdigest(), "baseline": baseline, "files": files, "can_apply": allow_publish}, contents


def apply_new(source, contents):
    # Preflight all conflicts before copying. A retry may encounter files from
    # an interrupted earlier copy; only their exact reviewed bytes are accepted.
    pending = []
    for relative, data in contents.items():
        path = tools.resolve_in_workspace(source, relative)
        if path.exists():
            old, _ = project_files.text_file(source, relative)
            if old != data:
                raise ValueError("Project already contains a conflicting file. Existing files were preserved.")
        else:
            pending.append((relative, data))
    for relative, data in pending:
        project_files.write_file(source, relative, data, make_parents=True)
    return len(contents)


def apply_verified(source, changes, contents, *, root_identity):
    head = git_read(source, None, ["rev-parse", "HEAD"])
    if head.returncode or head.stdout.decode("ascii").strip() != changes["baseline"]:
        raise ValueError("The destination Git revision changed. The validated worktree is preserved.")
    pending = []
    for item in changes["files"]:
        relative, before = item["path"], item["before"]
        target = tools.resolve_in_workspace(source, relative)
        if target.exists():
            raw, _ = project_files.text_file(source, relative)
            if raw == contents[relative]:
                continue
            if before is None or project_files.digest(raw) != before:
                raise ValueError(f"Destination has conflicting edits in {relative}. The validated worktree is preserved.")
        elif before is not None:
            raise ValueError(f"Tracked destination file {relative} disappeared. The validated worktree is preserved.")
        pending.append(item)
    # Exclusive creation and a second digest check on replacement protect changes
    # made after the preflight. A failed multi-file delivery keeps the worktree.
    written = []
    try:
        for item in pending:
            relative = item["path"]
            project_files.write_file(source, relative, contents[relative], expected=item["before"],
                                     make_parents=True, root_identity=root_identity)
            written.append(relative)
    except (ValueError, OSError) as error:
        detail = ", ".join(written) or "none"
        raise ValueError(f"Delivery interrupted. Files written this attempt: {detail}. "
                         "The validated worktree is preserved.") from error
    return list(contents)
