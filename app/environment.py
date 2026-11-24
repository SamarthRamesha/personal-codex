"""Project environment readiness: what a project declares, and what is still missing.

The coding workflows could tell the owner that a validation command failed, but not *why the
first step failed*: a Node project with no ``node_modules``, a Python project with no virtual
environment, or a dev script whose port was never declared. This module answers that question.

It reports; it never acts. Concretely:

- Read-only. It stats a short, fixed list of well-known paths and parses at most one bounded
  ``package.json``. It never reads a lockfile, source file, ``.env`` or credential, and it never
  executes a command, opens a socket or downloads anything.
- No guesses presented as facts. An installed-dependency state that has no local marker is
  ``unknown`` with the reason, and a dev-server port is reported only when the declared script
  itself contains one.
- Never a shell. Every reported command is one argv-splittable line with no shell operators, so
  it can be handed to the approved command runner unchanged.

Standard library only.
"""
from __future__ import annotations

import json
import re
import stat
from pathlib import Path

# A manifest bigger than this is not a manifest; it is reported as unread rather than parsed.
MAX_MANIFEST_BYTES = 200_000
DEV_SCRIPT_NAMES = ("dev", "serve", "start", "preview")
PORT_RE = re.compile(r"--port[= ]+(\d{2,5})\b")
ENV_PORT_RE = re.compile(r"\bPORT[= ]+(\d{2,5})\b")

# The lockfile decides the install command; without one the command has to resolve versions.
NODE_MANAGERS = (
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
)
NODE_RUNNERS = {"npm": "npm run", "pnpm": "pnpm run", "yarn": "yarn", "bun": "bun run"}
ADVISORIES = (
    "This report is read-only: nothing was installed, started or downloaded.",
    "Run a command yourself, or request it through the approved command runner; each listed "
    "command is a single command with no shell operators.",
)


def _is_regular(path: Path) -> bool:
    """A real file, not a symlink to one. Symlinks can point outside the project."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _is_directory(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


def _first_existing(root: Path, names) -> str | None:
    for name in names:
        if _is_regular(root / name):
            return name
    return None


def _declared_dev_scripts(root: Path, manager: str) -> tuple[list[dict], list[str], str | None]:
    """Parse the bounded package.json for dev/serve scripts; return (servers, notes, error).

    Only the ``scripts`` object is used. A package.json that is too large, unreadable or not
    JSON is reported as such instead of being half-interpreted.
    """
    path = root / "package.json"
    try:
        size = path.lstat().st_size
    except OSError as error:
        return [], [f"package.json could not be examined ({type(error).__name__})"], "unreadable"
    if size > MAX_MANIFEST_BYTES:
        return [], [f"package.json is {size} bytes, above the {MAX_MANIFEST_BYTES}-byte read "
                    "limit; its scripts were not parsed"], "too large"
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as error:
        return [], [f"package.json could not be parsed as JSON ({type(error).__name__}); "
                    "its scripts were not read"], "invalid JSON"
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return [], [], None
    servers = []
    for name in DEV_SCRIPT_NAMES:
        command = scripts.get(name)
        if not isinstance(command, str) or not command.strip():
            continue
        text = " ".join(command.split())
        match = PORT_RE.search(text) or ENV_PORT_RE.search(text)
        servers.append({"script": name, "declared": text[:400],
                        "command": f"{NODE_RUNNERS[manager]} {name}",
                        "port": int(match.group(1)) if match else None})
    return servers, [], None


def _node(root: Path) -> dict:
    lockfile = _first_existing(root, [name for name, _ in NODE_MANAGERS])
    manager = dict(NODE_MANAGERS).get(lockfile, "npm") if lockfile else "npm"
    if lockfile:
        steps = [{"manager": manager, "command": "npm ci" if manager == "npm" else f"{manager} install --frozen-lockfile"}]
    else:
        steps = [{"manager": "npm", "command": "npm install"}]
    entry: dict = {"kind": "node", "manifest": "package.json", "lockfile": lockfile,
                   "manager": manager, "install_steps": steps}
    if _is_directory(root / "node_modules"):
        entry.update(dependencies="installed", evidence="a node_modules directory exists")
    else:
        entry.update(dependencies="missing",
                     evidence="no node_modules directory; the project's own checks will fail "
                              "until its dependencies are installed")
    servers, notes, parse_error = _declared_dev_scripts(root, manager)
    entry["dev_servers"] = servers
    entry["notes"] = notes
    if parse_error:
        entry["manifest_problem"] = parse_error
    if servers and all(item["port"] is None for item in servers):
        entry["notes"] = notes + ["no dev script declares a port; the project's own default applies"]
    return entry


def _python(root: Path) -> dict:
    manifest = _first_existing(root, ["requirements.txt", "pyproject.toml", "Pipfile"])
    lockfile = _first_existing(root, ["uv.lock", "poetry.lock", "Pipfile.lock"])
    if lockfile == "uv.lock":
        steps = [{"manager": "uv", "command": "uv sync --frozen"}]
    elif lockfile == "poetry.lock":
        steps = [{"manager": "poetry", "command": "poetry install"}]
    elif lockfile == "Pipfile.lock":
        steps = [{"manager": "pipenv", "command": "pipenv sync"}]
    else:
        # Two separate commands, because one approved command cannot chain another.
        steps = [{"manager": "venv", "command": "python3 -m venv .venv"}]
        if manifest == "requirements.txt":
            steps.append({"manager": "pip", "command": ".venv/bin/pip install -r requirements.txt"})
        elif manifest == "pyproject.toml":
            steps.append({"manager": "pip", "command": ".venv/bin/pip install -e ."})
    entry: dict = {"kind": "python", "manifest": manifest, "lockfile": lockfile, "install_steps": steps}
    venv = next((name for name in (".venv", "venv") if _is_directory(root / name)), None)
    if venv:
        entry.update(dependencies="installed",
                     evidence=f"a {venv} directory exists (its interpreter was not run)")
    else:
        entry.update(dependencies="missing",
                     evidence="no .venv or venv directory; a system interpreter would be used "
                              "instead of the project's own environment")
    servers = []
    if _is_regular(root / "manage.py"):
        servers.append({"script": "runserver", "declared": "manage.py exists",
                        "command": "python3 manage.py runserver", "port": None})
    entry["dev_servers"] = servers
    entry["notes"] = ["Django's own default port applies to manage.py runserver"] if servers else []
    return entry


def _rust(root: Path) -> dict:
    entry: dict = {"kind": "rust", "manifest": "Cargo.toml",
                   "lockfile": _first_existing(root, ["Cargo.lock"]),
                   "install_steps": [{"manager": "cargo", "command": "cargo fetch"}]}
    if _is_directory(root / "target"):
        entry.update(dependencies="unknown",
                     evidence="a target directory exists; it does not prove the registry cache "
                              "is complete, because cargo resolves on build")
    else:
        entry.update(dependencies="unknown",
                     evidence="cargo downloads crates during a build; no local marker proves it")
    entry["dev_servers"], entry["notes"] = [], []
    return entry


def _go(root: Path) -> dict:
    entry: dict = {"kind": "go", "manifest": "go.mod",
                   "lockfile": _first_existing(root, ["go.sum"]),
                   "install_steps": [{"manager": "go", "command": "go mod download"}],
                   "dependencies": "unknown",
                   "evidence": "module downloads are not marked locally in a way this report can "
                               "verify without running go",
                   "dev_servers": [], "notes": []}
    return entry


def _summary(ecosystems: list[dict]) -> str:
    if not ecosystems:
        return ("No recognised project manifest was found (package.json, requirements.txt, "
                "pyproject.toml, Pipfile, Cargo.toml, go.mod).")
    parts = []
    for entry in ecosystems:
        state = entry["dependencies"]
        command = entry["install_steps"][0]["command"]
        if state == "missing":
            parts.append(f"{entry['kind']}: dependencies are missing — run `{command}` first")
        elif state == "installed":
            parts.append(f"{entry['kind']}: dependencies appear installed")
        else:
            parts.append(f"{entry['kind']}: dependency state is unverified")
    return "; ".join(parts) + "."


def inspect(root) -> dict:
    """Report one project's declared environment. Read-only; raises ValueError for a bad root."""
    path = Path(root).expanduser()
    if not path.is_dir():
        raise ValueError("Project path must be an existing directory")
    root = path.resolve()
    ecosystems = []
    if _is_regular(root / "package.json"):
        ecosystems.append(_node(root))
    if any(_is_regular(root / name) for name in ("requirements.txt", "pyproject.toml", "Pipfile")):
        ecosystems.append(_python(root))
    if _is_regular(root / "Cargo.toml"):
        ecosystems.append(_rust(root))
    if _is_regular(root / "go.mod"):
        ecosystems.append(_go(root))
    # Only the paths named above were examined; that is stated rather than implied.
    inspected = ["package.json"] if _is_regular(root / "package.json") else []
    return {"path": str(root), "executed": False, "network": False,
            "ecosystems": ecosystems, "summary": _summary(ecosystems),
            "advisories": list(ADVISORIES), "inspected": inspected,
            "limits": {"manifest_bytes": MAX_MANIFEST_BYTES,
                       "reads_lockfiles": False, "declared_scripts_only": True,
                       "unknown_dependency_state_is_reported": True},
            "scope": "declared manifests and local dependency markers only"}
