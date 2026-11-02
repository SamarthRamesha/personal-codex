"""Strict, allowlisted agent tool calls confined to one task workspace.

The model never receives filesystem or process authority. It returns a JSON
proposal, this module validates it against a closed schema, the control plane
binds an approval to the exact digest and file hashes, and only then does an
approved execution touch the workspace. `run_tests` is delegated to the
control plane's existing command executor, so no new execution capability is
introduced here.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import tempfile
from pathlib import Path

MAX_OPERATIONS = 8
MAX_READ_BYTES = 20_000
MAX_LIST_ENTRIES = 100
MAX_LIST_DEPTH = 3
MAX_PATCH_TEXT = 60_000
MAX_SUMMARY = 2_000
MAX_DIFF_LINES = 400
MAX_DIFF_CHARS = 60_000
IGNORED_PARTS = {".git", "node_modules", ".venv", "venv", "dist", "build", "target", "__pycache__"}
SECRET_NAMES = {".env", ".env.local", ".env.production", ".env.development", "id_rsa", "id_ed25519", "credentials.json"}

TOOL_SPECS = {
    "list_files": ({"path"}, {"depth", "limit"}),
    "read_file": ({"path"}, {"max_bytes"}),
    "apply_patch": ({"path", "old_text", "new_text"}, {"expected_sha256"}),
    "run_tests": ({"command"}, {"timeout"}),
}


class ToolCallError(ValueError):
    """A rejected or failed tool call; safe to show to the operator."""


def _is_secret(name: str) -> bool:
    return name in SECRET_NAMES or name.startswith(".env.")


def resolve_in_workspace(root: Path, relative) -> Path:
    """Resolve a model-supplied path, refusing escapes, symlink escapes, and secrets."""
    if not isinstance(relative, str) or not relative.strip():
        raise ToolCallError("Tool path must be a non-empty relative path")
    if relative.startswith("/") or relative.startswith("~"):
        raise ToolCallError("Tool paths must be relative to the task workspace")
    parts = Path(relative).parts
    if ".." in parts:
        raise ToolCallError("Tool paths must not contain '..'")
    if any(part in IGNORED_PARTS for part in parts):
        raise ToolCallError("Tool path targets an excluded directory")
    if any(_is_secret(part) for part in parts):
        raise ToolCallError("Tool path targets a secret-named file")
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ToolCallError("Tool path escapes the task workspace")
    return candidate


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def proposal_digest(task_id: str, workspace_branch: str, operations: list) -> str:
    canonical = json.dumps({"task_id": task_id, "workspace_branch": workspace_branch, "operations": operations},
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_str(op: dict, key: str, limit: int) -> str:
    value = op.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolCallError(f"{op.get('tool')} requires a non-empty string '{key}'")
    if len(value) > limit:
        raise ToolCallError(f"{op.get('tool')} '{key}' exceeds {limit} characters")
    return value


def _require_int(op: dict, key: str, low: int, high: int, default):
    value = op.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolCallError(f"{op.get('tool')} '{key}' must be an integer")
    if not low <= value <= high:
        raise ToolCallError(f"{op.get('tool')} '{key}' must be between {low} and {high}")
    return value


def validate_operations(operations) -> list[dict]:
    """Validate a closed-schema tool proposal; return normalised operations."""
    if not isinstance(operations, list) or not operations:
        raise ToolCallError("A proposal must contain a non-empty 'operations' list")
    if len(operations) > MAX_OPERATIONS:
        raise ToolCallError(f"A proposal may contain at most {MAX_OPERATIONS} operations")
    normalised = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ToolCallError(f"Operation {index + 1} must be a JSON object")
        tool = operation.get("tool")
        if tool not in TOOL_SPECS:
            raise ToolCallError(f"Operation {index + 1} uses an unsupported tool")
        required, optional = TOOL_SPECS[tool]
        keys = set(operation) - {"tool"}
        unknown = keys - required - optional
        if unknown:
            raise ToolCallError(f"{tool} does not accept: {', '.join(sorted(unknown))}")
        missing = required - keys
        if missing:
            raise ToolCallError(f"{tool} requires: {', '.join(sorted(missing))}")
        entry = {"tool": tool}
        if tool == "list_files":
            entry["path"] = _require_str(operation, "path", 400)
            entry["depth"] = _require_int(operation, "depth", 0, MAX_LIST_DEPTH, 1)
            entry["limit"] = _require_int(operation, "limit", 1, MAX_LIST_ENTRIES, 50)
        elif tool == "read_file":
            entry["path"] = _require_str(operation, "path", 400)
            entry["max_bytes"] = _require_int(operation, "max_bytes", 1, MAX_READ_BYTES, MAX_READ_BYTES)
        elif tool == "apply_patch":
            entry["path"] = _require_str(operation, "path", 400)
            entry["old_text"] = _require_str(operation, "old_text", MAX_PATCH_TEXT)
            entry["new_text"] = operation.get("new_text")
            if not isinstance(entry["new_text"], str):
                raise ToolCallError("apply_patch requires a string 'new_text'")
            if len(entry["new_text"]) > MAX_PATCH_TEXT:
                raise ToolCallError(f"apply_patch 'new_text' exceeds {MAX_PATCH_TEXT} characters")
            if entry["old_text"] == entry["new_text"]:
                raise ToolCallError("apply_patch must actually change the file")
            expected = operation.get("expected_sha256")
            if expected is not None and (not isinstance(expected, str) or len(expected) != 64):
                raise ToolCallError("apply_patch 'expected_sha256' must be a 64-character digest")
            entry["expected_sha256"] = expected
        elif tool == "run_tests":
            entry["command"] = _require_str(operation, "command", 500)
            entry["timeout"] = _require_int(operation, "timeout", 1, 300, 120)
        normalised.append(entry)
    return normalised


def bind_hashes(root: Path, operations: list[dict]) -> list[dict]:
    """Attach the current digest of every file an apply_patch would modify."""
    bound = []
    for operation in operations:
        if operation["tool"] == "apply_patch":
            target = resolve_in_workspace(root, operation["path"])
            if not target.is_file():
                raise ToolCallError(f"apply_patch target does not exist: {operation['path']}")
            operation = {**operation, "expected_sha256": file_sha256(target)}
        bound.append(operation)
    return bound


def list_files(root: Path, path: str, depth: int, limit: int) -> dict:
    base = resolve_in_workspace(root, path)
    if not base.is_dir():
        raise ToolCallError("list_files path is not a directory")
    entries, truncated = [], False
    for current, directories, files in os.walk(base):
        current_path = Path(current)
        depth_here = len(current_path.relative_to(base).parts)
        directories[:] = sorted(d for d in directories if d not in IGNORED_PARTS)
        if depth_here >= depth:
            directories[:] = []
        for name in sorted(files):
            if _is_secret(name):
                continue
            target = current_path / name
            if not target.is_file() or target.is_symlink():
                continue
            if len(entries) >= limit:
                truncated = True
                break
            entries.append({"path": str(target.relative_to(Path(root).resolve())), "bytes": target.stat().st_size})
        if truncated:
            break
    return {"path": path, "entries": entries, "truncated": truncated}


def read_file(root: Path, path: str, max_bytes: int) -> dict:
    target = resolve_in_workspace(root, path)
    if not target.is_file():
        raise ToolCallError(f"read_file target does not exist: {path}")
    size = target.stat().st_size
    data = target.read_bytes()[:max_bytes]
    return {"path": path, "bytes": size, "truncated": size > len(data), "sha256": file_sha256(target),
            "text": data.decode("utf-8", errors="replace")}


def apply_patch(root: Path, path: str, old_text: str, new_text: str, expected_sha256: str) -> dict:
    target = resolve_in_workspace(root, path)
    if not target.is_file():
        raise ToolCallError(f"apply_patch target does not exist: {path}")
    before = file_sha256(target)
    if expected_sha256 and before != expected_sha256:
        raise ToolCallError("File changed after review; request a new proposal and approval")
    original = target.read_bytes().decode("utf-8", errors="replace")
    occurrences = original.count(old_text)
    if occurrences != 1:
        raise ToolCallError(f"apply_patch expected exactly one match in {path}, found {occurrences}")
    updated = original.replace(old_text, new_text, 1)
    directory = target.parent
    handle, temporary = tempfile.mkstemp(dir=str(directory), prefix=".codex-patch-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(updated)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"path": path, "sha256_before": before, "sha256_after": file_sha256(target),
            "bytes_before": len(original.encode("utf-8")), "bytes_after": len(updated.encode("utf-8"))}


def review_operations(root: Path, operations: list[dict]) -> dict:
    """Build the reviewer's view of a pending proposal without touching the workspace.

    Each ``apply_patch`` entry reports the digest the proposal was bound to, the digest the file has
    now, and a bounded unified diff. A file whose digest no longer matches is marked stale so the
    dashboard can refuse to execute a review that no longer describes reality.
    """
    files, additions, deletions = [], 0, 0
    stale = False
    budget = MAX_DIFF_CHARS
    for operation in operations:
        if operation.get("tool") != "apply_patch":
            continue
        entry = {"path": operation["path"], "expected_sha256": operation.get("expected_sha256"),
                 "sha256_current": None, "stale": False, "occurrences": None, "diff": [],
                 "truncated": False, "error": None, "patch_preview_only": False}
        try:
            target = resolve_in_workspace(root, operation["path"])
            if not target.is_file():
                raise ToolCallError("review target no longer exists")
            current = target.read_bytes().decode("utf-8", errors="replace")
            entry["sha256_current"] = file_sha256(target)
            entry["stale"] = bool(operation.get("expected_sha256")) and entry["sha256_current"] != operation["expected_sha256"]
            occurrences = current.count(operation["old_text"])
            entry["occurrences"] = occurrences
            if occurrences == 1:
                before, after = current, current.replace(operation["old_text"], operation["new_text"], 1)
            else:
                before, after = operation["old_text"], operation["new_text"]
                entry["patch_preview_only"] = True
            delta = list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                              fromfile=f"a/{operation['path']}", tofile=f"b/{operation['path']}",
                                              lineterm="", n=3))
            for line in delta:
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1
            kept = []
            for line in delta[:MAX_DIFF_LINES]:
                size = len(line.encode("utf-8"))
                if budget - size < 0:
                    entry["truncated"] = True
                    break
                kept.append(line)
                budget -= size
            if len(delta) > len(kept):
                entry["truncated"] = True
            entry["diff"] = kept
        except (OSError, ValueError, ToolCallError) as error:
            entry["error"] = str(error)[:300]
            entry["stale"] = True
        stale = stale or entry["stale"] or bool(entry["error"])
        files.append(entry)
    return {"files": files, "stale": stale,
            "totals": {"files": len(files), "additions": additions, "deletions": deletions}}


def execute_operations(root: Path, operations: list[dict], runner=None, stop_check=None, on_event=None) -> dict:
    """Execute validated, approved operations sequentially; stop at the first failure or cancellation.

    `stop_check` is consulted before every operation, so a cancellation request is acted on before
    the next tool starts. `on_event(kind, index, operation, result)` lets the caller persist an
    operation-level ledger without giving the tools any storage authority. Completed operations are
    never replayed or rolled back: the partial result is returned with `cancelled` set.
    """
    results, failed, cancelled = [], False, False

    def notify(kind, index, operation, result):
        if on_event:
            on_event(kind, index, operation, result)

    for index, operation in enumerate(operations):
        tool = operation["tool"]
        if cancelled:
            results.append({"index": index, "tool": tool, "status": "cancelled",
                            "error": "cancelled before this operation started"})
            notify("finish", index, operation, results[-1])
            continue
        if failed:
            results.append({"index": index, "tool": tool, "status": "skipped"})
            notify("finish", index, operation, results[-1])
            continue
        if stop_check and stop_check():
            cancelled = True
            results.append({"index": index, "tool": tool, "status": "cancelled",
                            "error": "cancelled before this operation started"})
            notify("finish", index, operation, results[-1])
            continue
        notify("start", index, operation, None)
        try:
            if tool == "list_files":
                detail = list_files(root, operation["path"], operation["depth"], operation["limit"])
            elif tool == "read_file":
                detail = read_file(root, operation["path"], operation["max_bytes"])
            elif tool == "apply_patch":
                detail = apply_patch(root, operation["path"], operation["old_text"], operation["new_text"],
                                     operation.get("expected_sha256", ""))
            elif tool == "run_tests":
                if runner is None:
                    raise ToolCallError("No command runner is configured for this execution")
                detail = runner(operation["command"], operation["timeout"])
                if detail.get("cancelled"):
                    # The command was stopped by the operator mid-run: that is a cancellation, not
                    # a test failure, and the remaining operations must not start.
                    cancelled = True
                    results.append({"index": index, "tool": tool, "status": "cancelled", **detail,
                                    "error": "cancelled while the command was running"})
                    notify("finish", index, operation, results[-1])
                    continue
                if detail.get("exit_code") != 0:
                    failed = True
            else:
                raise ToolCallError("Unsupported tool")
            results.append({"index": index, "tool": tool, "status": "error" if failed else "ok", **detail})
        except (OSError, ValueError) as error:
            failed = True
            results.append({"index": index, "tool": tool, "status": "error", "error": str(error)[:400]})
        notify("finish", index, operation, results[-1])
    return {"operations": results, "cancelled": cancelled,
            "ok": not failed and not cancelled and all(r["status"] == "ok" for r in results),
            "cancelled_at_index": next((r["index"] for r in results if r["status"] == "cancelled"), None)}


def parse_proposal(text: str) -> dict:
    """Extract and validate the strict JSON proposal returned by a provider."""
    if not isinstance(text, str) or not text.strip():
        raise ToolCallError("Provider returned an empty agent proposal")
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        raise ToolCallError("Provider output was not valid JSON; no operations were accepted")
    if not isinstance(payload, dict):
        raise ToolCallError("Provider proposal must be a JSON object")
    unknown = set(payload) - {"summary", "operations"}
    if unknown:
        raise ToolCallError(f"Provider proposal has unsupported keys: {', '.join(sorted(unknown))}")
    summary = payload.get("summary", "")
    if not isinstance(summary, str) or len(summary) > MAX_SUMMARY:
        raise ToolCallError("Provider proposal 'summary' must be a string of at most 2000 characters")
    return {"summary": summary, "operations": validate_operations(payload.get("operations"))}


def agent_instruction(workspace_files: list[str]) -> str:
    """Deterministic instruction block; the approval binds the resulting prompt digest."""
    listing = ", ".join(workspace_files[:60]) if workspace_files else "(empty workspace)"
    return (
        "You are the developer stage of a local coding agent. Propose the smallest safe change.\n"
        "Reply with JSON only, no prose, in this exact shape:\n"
        '{"summary":"one or two sentences","operations":[{"tool":"list_files","path":"."},'
        '{"tool":"read_file","path":"relative/path"},'
        '{"tool":"apply_patch","path":"relative/path","old_text":"exact existing text",'
        '"new_text":"replacement text"},{"tool":"run_tests","command":"python3 -m unittest discover -s tests"}]}\n'
        f"Allowed tools only: list_files, read_file, apply_patch, run_tests. At most {MAX_OPERATIONS} operations.\n"
        "Paths are relative to the task workspace. Never use absolute paths, '..', .git, .env, or secrets.\n"
        "apply_patch must match exactly once in the current file and must state the exact existing text.\n"
        "run_tests must use an allowlisted development command and will only run after human approval.\n"
        f"Visible workspace files: {listing}"
    )


ROUND_STATUSES = {"continue", "complete", "blocked", "failed"}
FEEDBACK_TAIL = 2000


def parse_round_proposal(text: str) -> dict:
    """Validate a round proposal: a completion status plus optional tool operations."""
    if not isinstance(text, str) or not text.strip():
        raise ToolCallError("Provider returned an empty agent proposal")
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        raise ToolCallError("Provider output was not valid JSON; no operations were accepted")
    if not isinstance(payload, dict):
        raise ToolCallError("Provider proposal must be a JSON object")
    unknown = set(payload) - {"summary", "status", "operations"}
    if unknown:
        raise ToolCallError(f"Provider proposal has unsupported keys: {', '.join(sorted(unknown))}")
    status = payload.get("status", "continue")
    if status not in ROUND_STATUSES:
        raise ToolCallError("Provider 'status' must be one of: continue, complete, blocked, failed")
    summary = payload.get("summary", "")
    if not isinstance(summary, str) or len(summary) > MAX_SUMMARY:
        raise ToolCallError("Provider proposal 'summary' must be a string of at most 2000 characters")
    raw = payload.get("operations")
    if status == "continue":
        return {"status": status, "summary": summary, "operations": validate_operations(raw)}
    if raw not in (None, []):
        raise ToolCallError("A terminal round status must not carry operations")
    return {"status": status, "summary": summary, "operations": []}


def round_feedback(root: Path, operations: list, results: list, redact=None) -> dict:
    """Summarise what a round actually did so the next round can react to evidence."""
    redact = redact or (lambda value: value)
    tests, changed, errors = [], [], []
    for result in results:
        index = result.get("index", 0)
        operation = operations[index] if 0 <= index < len(operations) else {}
        if result["tool"] == "run_tests":
            tests.append({"command": operation.get("command", ""), "exit_code": result.get("exit_code"),
                          "output": redact(str(result.get("output", "")))[-FEEDBACK_TAIL:]})
        if result["tool"] == "apply_patch" and result["status"] == "ok":
            changed.append(operation.get("path", ""))
        if result["status"] != "ok":
            errors.append(f"{result['tool']}: {str(result.get('error') or 'exit ' + str(result.get('exit_code')))[:200]}")
    last = tests[-1] if tests else None
    failed_names = []
    if last:
        for line in str(last["output"]).splitlines():
            stripped = line.strip()
            if stripped.startswith(("FAIL:", "FAILED ", "ERROR:")):
                failed_names.append(stripped[:160])
    return {
        "test_command": last["command"] if last else None,
        "test_exit_code": last["exit_code"] if last else None,
        "test_output": last["output"] if last else "",
        "tests_ran": bool(tests),
        "changed_files": changed,
        "failed_tests": failed_names[:10],
        "errors": errors[:8],
        "ok": all(result["status"] == "ok" for result in results),
    }


def completion_evidence(rounds: list) -> tuple[bool, str]:
    """A model may not declare success without executed work and a passing test run."""
    executed = [r for r in rounds if r["status"] in {"passed", "failed-checks"}]
    if not executed:
        return False, "no executed round with recorded evidence yet"
    passing = [r for r in rounds if r["status"] == "passed" and r.get("test_result")]
    if not any(r["test_result"].get("tests_ran") and r["test_result"].get("test_exit_code") == 0 for r in passing):
        return False, "completion requires at least one executed round with a passing test command"
    if not any(r["test_result"].get("changed_files") for r in passing):
        return False, "completion requires at least one approved file change"
    latest = executed[-1]
    if latest["status"] != "passed":
        return False, "the most recent executed round did not pass its checks"
    return True, "latest executed round passed with recorded file changes"
