#!/usr/bin/env python3
"""Personal Codex local control plane. Standard-library only by design for v0."""
from __future__ import annotations

import hashlib, json, os, re, resource, shlex, signal, sqlite3, subprocess, sys, tempfile, time, uuid
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    import providers, tools  # script execution puts app/ on sys.path
    from providers import ProviderTransportError
    from providers import openai_transport, OllamaTransport, transport_for  # noqa: F401 (re-exported for tests)
except ImportError:  # imported as app.server
    from app import providers, tools
    from app.providers import ProviderTransportError
    from app.providers import openai_transport, OllamaTransport, transport_for  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB_PATH = DATA / "personal_codex.db"
WEB = ROOT / "web"
SECRET_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "credentials.json"}
ALLOWED_COMMANDS = {"git", "python", "python3", "pytest", "npm", "node", "cargo", "rustc", "go", "make"}
MAX_TIMEOUT_SECONDS = 300
MAX_OUTPUT_BYTES = 200_000
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_MEMORY_BYTES = 768 * 1024 * 1024
MAX_ROUNDS = max(1, min(10, int(os.getenv("PERSONAL_CODEX_MAX_ROUNDS", "3") or "3")))
MAX_TASK_SECONDS = 1800
ROUND_ACTIVE = {"awaiting-approval", "executing"}
PROVIDER_KINDS = {"ollama", "openai-compatible"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
ENV_REF_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, prompt TEXT NOT NULL, status TEXT NOT NULL, plan TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, agent TEXT NOT NULL, level TEXT NOT NULL, message TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS providers (id TEXT PRIMARY KEY, kind TEXT NOT NULL, endpoint TEXT, model TEXT, secret_ref TEXT, cloud_allowed INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS workspaces (task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, path TEXT NOT NULL UNIQUE, branch TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS executions (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, argv TEXT NOT NULL, exit_code INTEGER, output TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS invocations (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, provider_id TEXT NOT NULL, prompt_sha256 TEXT NOT NULL, response TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, workspace_branch TEXT NOT NULL, workspace_path TEXT NOT NULL, summary TEXT NOT NULL, operations TEXT NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL, results TEXT, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS rounds (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, round_number INTEGER NOT NULL, provider_id TEXT NOT NULL, model TEXT NOT NULL, prompt_sha256 TEXT NOT NULL, proposal_id TEXT, proposal_digest TEXT, approval_id TEXT, status TEXT NOT NULL, summary TEXT, operations TEXT, results TEXT, test_result TEXT, error TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
"""

def now() -> int: return int(time.time())
def uid() -> str: return str(uuid.uuid4())

class Store:
    def __init__(self):
        DATA.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA); self.conn.commit()
    def rows(self, sql, args=()): return [dict(x) for x in self.conn.execute(sql, args).fetchall()]
    def one(self, sql, args=()):
        row = self.conn.execute(sql, args).fetchone(); return dict(row) if row else None
    def write(self, sql, args=()): self.conn.execute(sql, args); self.conn.commit()

STORE = Store()

def safe_project_path(value: str) -> Path:
    p = Path(value).expanduser().resolve()
    if not p.exists() or not p.is_dir(): raise ValueError("Project path must be an existing directory")
    return p

def validate_provider_config(kind: str, endpoint: str, model: str, secret_ref: str, cloud_allowed: bool) -> dict:
    """Validate metadata only; this function never reads an environment secret or contacts a provider."""
    if kind not in PROVIDER_KINDS: raise ValueError("Unsupported provider kind")
    if not model: raise ValueError("model is required")
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Provider endpoint must be an absolute http(s) URL without embedded credentials")
    if not cloud_allowed and parsed.hostname.lower() not in LOOPBACK_HOSTS:
        raise ValueError("Non-cloud providers must use a loopback endpoint; cloud use requires explicit consent")
    if secret_ref and not ENV_REF_RE.fullmatch(secret_ref):
        raise ValueError("secret_ref must be an environment-variable name, never a secret value")
    return {"kind": kind, "endpoint": endpoint, "model": model, "secret_ref": secret_ref, "cloud_allowed": int(cloud_allowed)}

def provider_capabilities(provider: dict) -> dict:
    """Describe the adapter boundary without invoking a provider or reading a secret."""
    return {"id": provider["id"], "kind": provider["kind"], "endpoint": provider["endpoint"], "model": provider["model"], "cloud_allowed": bool(provider["cloud_allowed"]), "supports_streaming": True, "supports_tool_calls": provider["kind"] == "openai-compatible", "invocation_requires_approval": True}

def validate_provider_prompt(prompt) -> str:
    """Reject empty or oversized provider requests before any approval or transport use."""
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20_000: raise ValueError("Provider prompt must contain 1–20000 characters")
    return prompt

def provider_invocation_detail(task_id: str, provider: dict, prompt: str) -> str:
    """Bind an approval to exact non-secret provider metadata and request bytes."""
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return approval_detail("provider-invoke", task_id, provider_id=provider["id"], endpoint=provider["endpoint"], model=provider["model"], prompt_sha256=digest, cloud_allowed=bool(provider["cloud_allowed"]))

def provider_approval_kind(provider: dict) -> str:
    """A cloud transmission needs its own network consent; a loopback call needs invocation approval only."""
    return "network" if provider["cloud_allowed"] else "provider-invoke"

def unavailable_provider_transport(request: dict) -> dict:
    """Optional fail-closed transport for tests and hardened deployments."""
    raise ValueError("No approved provider transport is configured; real network invocation is not implemented")

# None means: use the built-in Ollama/OpenAI-compatible adapters in app/providers.py.
# Set to a callable to inject a deterministic transport (tests, offline deployments).
PROVIDER_TRANSPORT = None

def active_provider_transport(provider: dict):
    """Resolve the transport per invocation so credentials are read only at call time."""
    if PROVIDER_TRANSPORT is not None: return PROVIDER_TRANSPORT
    return providers.transport_for(provider, provider.get("secret_ref") or "")

def provider_row(provider_id):
    return STORE.one("SELECT id,kind,endpoint,model,cloud_allowed,enabled,secret_ref FROM providers WHERE id=?",(provider_id,))

def build_agent_prompt(task: dict, workspace: dict, extra: str = "") -> str:
    """Deterministic agent instruction so an approval binds one exact prompt."""
    listing=[entry["path"] for entry in tools.list_files(Path(workspace["path"]), ".", 1, 60)["entries"]]
    prompt=tools.agent_instruction(listing)+f"\nTask: {str(task['prompt'])[:2000]}"
    if extra: prompt+=f"\nExtra instructions: {extra[:2000]}"
    return prompt

def task_rounds(task_id: str) -> list:
    return STORE.rows("SELECT * FROM rounds WHERE task_id=? ORDER BY round_number ASC", (task_id,))

def decoded_rounds(task_id: str) -> list:
    """Rounds with their JSON columns decoded for reporting and completion evidence."""
    result = []
    for row in task_rounds(task_id):
        entry = dict(row)
        for key in ("operations", "results", "test_result"):
            entry[key] = json.loads(entry[key]) if entry.get(key) else ([] if key != "test_result" else None)
        result.append(entry)
    return result

def round_history_text(rounds: list) -> str:
    """Deterministic, bounded evidence so a round approval binds the exact history."""
    if not rounds: return "No rounds executed yet."
    lines = []
    for entry in rounds:
        line = f"Round {entry['round_number']}: {entry['status']}"
        if entry["summary"]: line += f" — {entry['summary'][:300]}"
        test = entry["test_result"] if isinstance(entry.get("test_result"), dict) else None
        if test:
            line += f"; test={test.get('test_command')} exit={test.get('test_exit_code')}"
            if test.get("failed_tests"): line += f"; failures={'; '.join(test['failed_tests'][:5])}"
            if test.get("test_output"): line += f"; output={test['test_output'][-600:]}"
        if entry.get("error"): line += f"; error={entry['error'][:300]}"
        lines.append(line)
    return "\n".join(lines)

def build_round_prompt(task: dict, workspace: dict, extra: str = "", rounds: list = ()) -> str:
    """Deterministic iterative instruction; history is part of the approved prompt bytes."""
    listing = [entry["path"] for entry in tools.list_files(Path(workspace["path"]), ".", 1, 60)["entries"]]
    prompt = tools.agent_instruction(listing)
    prompt += ("\n\nRound protocol: reply with JSON only: "
               '{"summary":"one or two sentences","status":"continue|complete|blocked|failed","operations":[...]}'
               "\nUse 'continue' with 1-8 operations for the next change, 'complete' only when the task is finished and the recorded checks pass, "
               "'blocked' when a human decision or external dependency is required, and 'failed' when it cannot continue safely. "
               "A terminal status must not carry operations. Never repeat a change that already failed; react to the evidence below.")
    prompt += f"\nTask: {str(task['prompt'])[:2000]}"
    prompt += f"\nExecution history:\n{round_history_text(rounds)}"
    if extra: prompt += f"\nExtra instructions: {extra[:2000]}"
    return prompt

def round_invocation_detail(task_id: str, provider: dict, prompt: str, round_number: int) -> str:
    """A round approval binds the exact prompt bytes and the round they were produced for."""
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return approval_detail("provider-invoke", task_id, provider_id=provider["id"], endpoint=provider["endpoint"], model=provider["model"], prompt_sha256=digest, round=round_number, cloud_allowed=bool(provider["cloud_allowed"]))

def round_proposal_detail(task_id: str, round_number: int, workspace: dict, digest: str, prompt_sha256: str) -> str:
    return approval_detail("agent-round-proposal", task_id, round=round_number, workspace=workspace["branch"], workspace_path=workspace["path"], proposal=digest, prompt_sha256=prompt_sha256)

def round_limits(task_id: str) -> dict:
    rounds = task_rounds(task_id)
    used = len([r for r in rounds if r["status"] != "cancelled"])
    started = min([r["created_at"] for r in rounds], default=now())
    return {"max_rounds": MAX_ROUNDS, "rounds_used": used, "next_round": (max([r["round_number"] for r in rounds], default=0) + 1),
            "remaining": max(0, MAX_ROUNDS - used), "max_task_seconds": MAX_TASK_SECONDS, "elapsed_seconds": now() - started}

def round_budget_error(task_id: str) -> str | None:
    limits = round_limits(task_id)
    if limits["rounds_used"] >= MAX_ROUNDS: return f"round limit reached ({MAX_ROUNDS}); cancel or start a new task"
    if limits["elapsed_seconds"] > MAX_TASK_SECONDS: return f"task time limit reached ({MAX_TASK_SECONDS}s)"
    return None

def insert_round(task_id, number, provider, prompt_sha256, status, summary=None, proposal_id=None, proposal_digest=None,
                 approval_id=None, operations=None, results=None, test_result=None, error=None):
    rid = uid()
    stamp = now()
    STORE.write("INSERT INTO rounds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid, task_id, number, provider["id"], provider["model"], prompt_sha256, proposal_id, proposal_digest,
                 approval_id, status, summary, json.dumps(operations) if operations is not None else None,
                 json.dumps(results) if results is not None else None,
                 json.dumps(test_result) if test_result is not None else None, error, stamp, stamp))
    return rid

def task_report(task_id: str) -> dict:
    """Objective end-of-task summary built from recorded rounds, never from model prose."""
    task = STORE.one("SELECT * FROM tasks WHERE id=?", (task_id,))
    rounds = decoded_rounds(task_id)
    changed, tests = [], []
    for entry in rounds:
        test = entry["test_result"] or {}
        changed.extend(test.get("changed_files") or [])
        if test.get("tests_ran"):
            tests.append({"round": entry["round_number"], "command": test.get("test_command"),
                          "exit_code": test.get("test_exit_code"), "failed": test.get("failed_tests") or []})
    workspace = STORE.one("SELECT * FROM workspaces WHERE task_id=?", (task_id,))
    diff_summary = ""
    if workspace:
        diff_summary = redacted(git_output(workspace["path"], ["diff", "--stat", "HEAD"]).stdout)[:2000]
    latest = rounds[-1] if rounds else None
    return {"task_id": task_id, "status": task["status"] if task else "unknown", "rounds": len(rounds),
            "summary": latest["summary"] if latest else None, "changed_files": sorted({path for path in changed if path}),
            "tests": tests, "diff_summary": diff_summary, "limits": round_limits(task_id)}

def invoke_provider(provider: dict, prompt: str, transport) -> dict:
    """Adapter seam for approved callers; transport is injected so tests perform no I/O."""
    validate_provider_prompt(prompt)
    request = {"kind": provider["kind"], "endpoint": provider["endpoint"], "model": provider["model"], "prompt": prompt, "cloud_allowed": bool(provider.get("cloud_allowed"))}
    response = transport(request)
    if not isinstance(response, dict) or not isinstance(response.get("text"), str): raise ValueError("Provider transport returned an invalid response")
    return {"text": response["text"][:MAX_OUTPUT_BYTES], "model": provider["model"], "provider_id": provider["id"]}

def visible_files(root: Path, cap=160):
    result=[]
    ignored={".git", "node_modules", ".venv", "venv", "dist", "build", "target", "__pycache__"}
    for path in root.rglob("*"):
        if len(result) >= cap: break
        rel = path.relative_to(root)
        if any(part in ignored for part in rel.parts) or path.name in SECRET_NAMES: continue
        if path.is_file() and path.stat().st_size < 400_000: result.append(str(rel))
    return result

def repository_summary(root: Path) -> dict:
    files = visible_files(root)
    manifests = [x for x in files if Path(x).name in {"package.json","pyproject.toml","Cargo.toml","go.mod","requirements.txt","README.md"}]
    git = (root / ".git").exists()
    return {"path": str(root), "git": git, "file_count_sample": len(files), "files": files[:80], "manifests": manifests}

def plan_for(prompt: str, summary: dict) -> list[dict]:
    focus = summary["manifests"] or summary["files"][:5]
    return [
      {"agent":"planner", "action":"Inspect architecture and relevant files", "detail": ", ".join(focus[:6]) or "Repository is empty; establish a minimal foundation."},
      {"agent":"developer", "action":"Implement scoped change", "detail": prompt.strip()[:500]},
      {"agent":"testing", "action":"Run project-appropriate checks", "detail":"Commands require explicit execution approval before they run."},
      {"agent":"reviewer", "action":"Review diff and security boundaries", "detail":"Check secret redaction, unintended files, and regression risk."},
    ]

def task_event(task_id, agent, level, message):
    STORE.write("INSERT INTO events VALUES (?,?,?,?,?,?)", (uid(), task_id, agent, level, message, now()))

def parse_command(command: str) -> list[str]:
    """Parse an approved development command; shell syntax is deliberately forbidden."""
    argv = shlex.split(command)
    if not argv or argv[0] not in ALLOWED_COMMANDS: raise ValueError("Command is not in the controlled development allowlist")
    if any(x in {"|", ";", "&&", "||", ">", ">>"} or x.startswith("$") for x in argv):
        raise ValueError("Shell operators and substitutions are not permitted")
    return argv

def redacted(text: str) -> str:
    text = re.sub(r'(?i)(api[_-]?key|token|password|secret)\s*[=:]\s*[^\s]+', r'\1=[REDACTED]', text)
    return text[:MAX_OUTPUT_BYTES]

def workspace_path(task_id: str) -> Path:
    return (DATA / "workspaces" / task_id).resolve()

def create_task_workspace(task_id: str, project_path: str) -> dict:
    """Create an isolated branch. Caller must first satisfy a matching approval."""
    root = Path(project_path).resolve(); target = workspace_path(task_id)
    if not (root / ".git").exists(): raise ValueError("A Git repository is required for isolated execution")
    if target.exists(): raise ValueError("Task workspace already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    branch = f"personal-codex/task-{task_id[:8]}"
    result = subprocess.run(["git", "-C", str(root), "worktree", "add", "-b", branch, str(target)], text=True, capture_output=True, timeout=45, check=False)
    if result.returncode != 0: raise ValueError(redacted(result.stderr or result.stdout or "worktree creation failed"))
    return {"path":str(target), "branch":branch}

def workspace_clean(path: str) -> bool:
    result = subprocess.run(["git", "-C", path, "status", "--porcelain"], text=True, capture_output=True, timeout=20, check=False)
    if result.returncode != 0: raise ValueError(redacted(result.stderr or "Unable to inspect workspace status"))
    return not result.stdout.strip()

def release_task_workspace(project_path: str, path: str) -> None:
    """Remove only a clean worktree. Its branch remains as the recovery checkpoint."""
    root, target = Path(project_path).resolve(), Path(path).resolve()
    if DATA.resolve() not in target.parents: raise ValueError("Workspace is outside the controlled storage root")
    if not workspace_clean(str(target)): raise ValueError("Workspace has uncommitted changes; preserve or commit them before release")
    result = subprocess.run(["git", "-C", str(root), "worktree", "remove", str(target)], text=True, capture_output=True, timeout=45, check=False)
    if result.returncode != 0: raise ValueError(redacted(result.stderr or result.stdout or "worktree release failed"))

def git_output(root: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", root, *args], text=True, capture_output=True, timeout=45, check=False)

def current_branch(root: str) -> str:
    result=git_output(root,["symbolic-ref","--quiet","--short","HEAD"])
    if result.returncode != 0: raise ValueError("Detached HEAD is not a merge target")
    return result.stdout.strip()

def ref_oid(root: str, ref: str) -> str:
    result = git_output(root, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if result.returncode != 0: raise ValueError(f"Git reference is unavailable: {ref}")
    return result.stdout.strip()

def approval_detail(action: str, task_id: str, **refs) -> str:
    """Canonical, immutable description of the exact Git state a user reviewed."""
    return json.dumps({"action": action, "refs": refs, "task_id": task_id}, sort_keys=True, separators=(",", ":"))

def merge_preview(root: str, branch: str) -> dict:
    if not workspace_clean(root): raise ValueError("Project has uncommitted changes; merge is refused")
    target = current_branch(root)
    target_oid, branch_oid = ref_oid(root, target), ref_oid(root, branch)
    result=git_output(root,["merge-tree","--write-tree",target,branch])
    preview = {"target": target, "target_oid": target_oid, "branch": branch, "branch_oid": branch_oid}
    if result.returncode == 0: return {**preview, "can_merge":True,"detail":"Merge tree is conflict-free."}
    return {**preview, "can_merge":False,"detail":redacted(result.stdout or result.stderr or "Merge conflict detected.")}

def merge_recovery_branch(root: str, branch: str, target: str, branch_oid: str, target_oid: str) -> None:
    if current_branch(root) != target or ref_oid(root, target) != target_oid or ref_oid(root, branch) != branch_oid:
        raise ValueError("Reviewed Git state changed after approval; request a new preview and approval")
    preview = merge_preview(root, branch)
    if not preview["can_merge"]: raise ValueError("Merge conflicts detected; resolve them manually in a dedicated workspace")
    result=git_output(root,["merge","--no-ff","--no-edit",branch])
    if result.returncode != 0: raise ValueError(redacted(result.stderr or result.stdout or "Merge failed"))

def delete_merged_branch(root: str, branch: str, branch_oid: str) -> None:
    if ref_oid(root, branch) != branch_oid: raise ValueError("Recovery branch changed after approval; request a new deletion approval")
    target=current_branch(root)
    contained=git_output(root,["merge-base","--is-ancestor",branch,target])
    if contained.returncode != 0: raise ValueError("Recovery branch is not merged into the current target")
    result=git_output(root,["branch","-d",branch])
    if result.returncode != 0: raise ValueError(redacted(result.stderr or result.stdout or "Branch deletion failed"))

def child_limits(timeout: int):
    """Apply limits that the host OS accepts; unsupported limits remain documented."""
    def cap(limit, wanted):
        try:
            _, hard = resource.getrlimit(limit)
            ceiling = min(wanted, hard)
            resource.setrlimit(limit, (ceiling, ceiling))
        except (OSError, ValueError):
            pass
    cap(resource.RLIMIT_CPU, min(timeout + 5, MAX_TIMEOUT_SECONDS + 5))
    cap(resource.RLIMIT_FSIZE, MAX_FILE_BYTES)
    cap(resource.RLIMIT_NOFILE, 64)
    if hasattr(resource, "RLIMIT_AS"): cap(resource.RLIMIT_AS, MAX_MEMORY_BYTES)

def execute_in_workspace(path: str, command: str, timeout=120) -> dict:
    try: timeout=int(timeout)
    except (TypeError, ValueError): raise ValueError("Timeout must be an integer")
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS: raise ValueError(f"Timeout must be between 1 and {MAX_TIMEOUT_SECONDS} seconds")
    argv=parse_command(command); root=Path(path).resolve()
    if not root.is_dir() or DATA.resolve() not in root.parents: raise ValueError("Execution must use a Personal Codex task workspace")
    env={"PATH":os.environ.get("PATH", ""), "HOME":str(root), "LANG":"C", "LC_ALL":"C"}
    runtime = DATA / "runtime"; runtime.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w+b", dir=runtime, delete=False) as output_file:
        output_path=Path(output_file.name)
    try:
        with output_path.open("ab") as output_file:
            process=subprocess.Popen(argv, cwd=root, env=env, stdout=output_file, stderr=subprocess.STDOUT, preexec_fn=lambda: child_limits(timeout), start_new_session=True)
            try: exit_code=process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(); exit_code=124
        output=output_path.read_bytes()[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        if exit_code == 124: output += "\nTimed out."
        return {"argv":argv,"exit_code":exit_code,"output":redacted(output)}
    finally:
        output_path.unlink(missing_ok=True)

class App(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args): print("[personal-codex] " + fmt % args)
    def json(self, payload, status=200):
        body=json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def body(self):
        length=int(self.headers.get("Content-Length",0)); return json.loads(self.rfile.read(length) or b"{}")
    def route(self): return urlparse(self.path).path
    def do_GET(self):
        route=self.route()
        if route == "/api/health": return self.json({"ok":True,"version":"0.1.0","mode":"local-control-plane"})
        if route == "/api/projects": return self.json(STORE.rows("SELECT * FROM projects ORDER BY created_at DESC"))
        if route == "/api/tasks": return self.json(STORE.rows("SELECT * FROM tasks ORDER BY updated_at DESC"))
        if route.startswith("/api/tasks/") and route.endswith("/events"):
            tid=route.split("/")[3]; return self.json(STORE.rows("SELECT * FROM events WHERE task_id=? ORDER BY created_at",(tid,)))
        if route == "/api/approvals": return self.json(STORE.rows("SELECT * FROM approvals WHERE status='pending' ORDER BY created_at DESC"))
        if route == "/api/providers": return self.json(STORE.rows("SELECT id,kind,endpoint,model,secret_ref,cloud_allowed,enabled,created_at FROM providers ORDER BY created_at DESC"))
        if route.startswith("/api/providers/") and route.endswith("/capabilities"):
            pid=route.split("/")[3]; provider=STORE.one("SELECT id,kind,endpoint,model,secret_ref,cloud_allowed,enabled,created_at FROM providers WHERE id=?",(pid,))
            return self.json(provider_capabilities(provider)) if provider else self.json({"error":"provider not found"},404)
        if route.startswith("/api/tasks/") and route.endswith("/workspace"):
            tid=route.split("/")[3]; return self.json(STORE.one("SELECT * FROM workspaces WHERE task_id=?",(tid,)) or {"task_id":tid,"status":"absent"})
        if route.startswith("/api/tasks/") and route.endswith("/workspace-recovery"):
            tid=route.split("/")[3]; workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=?",(tid,))
            if not workspace: return self.json({"error":"workspace not found"},404)
            present=Path(workspace["path"]).is_dir()
            clean=workspace_clean(workspace["path"]) if present else None
            return self.json({**workspace,"present":present,"clean":clean,"branch_preserved":True})
        if route.startswith("/api/tasks/") and route.endswith("/merge-preview"):
            tid=route.split("/")[3]; workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='released'",(tid,))
            if not workspace: return self.json({"error":"released workspace not found"},404)
            project=STORE.one("SELECT * FROM projects WHERE id=?",(workspace["project_id"],)); return self.json(merge_preview(project["path"],workspace["branch"]))
        if route.startswith("/api/tasks/") and route.endswith("/executions"):
            tid=route.split("/")[3]; return self.json(STORE.rows("SELECT * FROM executions WHERE task_id=? ORDER BY created_at DESC",(tid,)))
        if route.startswith("/api/tasks/") and route.endswith("/invocations"):
            tid=route.split("/")[3]; return self.json(STORE.rows("SELECT id,task_id,provider_id,prompt_sha256,response,created_at FROM invocations WHERE task_id=? ORDER BY created_at DESC",(tid,)))
        if route.startswith("/api/tasks/") and route.endswith("/agent/rounds"):
            tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
            if not task: return self.json({"error":"task not found"},404)
            return self.json({"task_id":tid,"status":task["status"],"limits":round_limits(tid),"rounds":decoded_rounds(tid)})
        if route.startswith("/api/tasks/") and route.endswith("/agent/report"):
            tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
            if not task: return self.json({"error":"task not found"},404)
            return self.json(task_report(tid))
        if route.startswith("/api/tasks/") and route.endswith("/agent"):
            tid=route.split("/")[3]; proposal=STORE.one("SELECT * FROM proposals WHERE task_id=? ORDER BY created_at DESC LIMIT 1",(tid,))
            if not proposal: return self.json({"task_id":tid,"status":"absent"})
            return self.json({**proposal,"operations":json.loads(proposal["operations"]),"results":json.loads(proposal["results"] or "[]")})
        if route.startswith("/api/projects/") and route.endswith("/summary"):
            pid=route.split("/")[3]; p=STORE.one("SELECT * FROM projects WHERE id=?",(pid,))
            return self.json(repository_summary(Path(p["path"]))) if p else self.json({"error":"not found"},404)
        return self.serve_static(route)
    def serve_static(self, route):
        name="index.html" if route in {"/",""} else route.lstrip("/")
        candidate=(WEB/name).resolve()
        if WEB not in candidate.parents or not candidate.is_file(): self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", "text/css" if name.endswith(".css") else "application/javascript" if name.endswith(".js") else "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(candidate.read_bytes())
    def do_POST(self):
        try:
            route=self.route(); data=self.body()
            if route == "/api/projects":
                path=safe_project_path(data.get("path","")); pid=uid(); name=data.get("name") or path.name
                STORE.write("INSERT INTO projects VALUES (?,?,?,?)",(pid,name,str(path),now())); return self.json({"id":pid,"name":name,"path":str(path)},201)
            if route == "/api/tasks":
                project=STORE.one("SELECT * FROM projects WHERE id=?",(data.get("project_id"),))
                if not project: return self.json({"error":"project not found"},404)
                prompt=str(data.get("prompt","")).strip()
                if not prompt: return self.json({"error":"task prompt is required"},400)
                plan=plan_for(prompt, repository_summary(Path(project["path"]))); tid=uid(); t=now()
                STORE.write("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)",(tid,project["id"],prompt,"planned",json.dumps(plan),t,t))
                task_event(tid,"planner","info","Repository summary completed; implementation plan created.")
                task_event(tid,"security","info","Secret-named files excluded from task context by default.")
                return self.json({"id":tid,"status":"planned","plan":plan},201)
            if route == "/api/approvals":
                project=STORE.one("SELECT * FROM projects WHERE id=?",(data.get("project_id"),))
                if not project: return self.json({"error":"project not found"},404)
                kind=str(data.get("kind","execute")); detail=str(data.get("detail",""))
                aid=uid(); STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(aid,project["id"],kind,detail,"pending",now())); return self.json({"id":aid,"status":"pending"},201)
            if route == "/api/providers":
                kind=str(data.get("kind","openai-compatible")); endpoint=str(data.get("endpoint","")).strip(); model=str(data.get("model","")).strip(); ref=str(data.get("secret_ref","")).strip()
                config=validate_provider_config(kind,endpoint,model,ref,data.get("cloud_allowed") is True)
                pid=uid(); STORE.write("INSERT INTO providers VALUES (?,?,?,?,?,?,?,?)",(pid,kind,endpoint,model,ref,config["cloud_allowed"],1,now()))
                return self.json({"id":pid,"capabilities":provider_capabilities({"id":pid,**config}),"note":"Only an environment-variable reference is stored; no secret value was accepted and no provider was contacted."},201)
            if route.startswith("/api/tasks/") and route.endswith("/workspace-request"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                aid=uid(); detail=f"workspace:{tid}"
                STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(aid,task["project_id"],"modify",detail,"pending",now()))
                task_event(tid,"security","info","Workspace creation requires approval.")
                return self.json({"id":aid,"status":"pending","detail":detail},201)
            if route.startswith("/api/tasks/") and route.endswith("/workspace"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,));
                if not task: return self.json({"error":"task not found"},404)
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind='modify' AND detail=? AND status='approved'",(task["project_id"],f"workspace:{tid}"))
                if not permitted: return self.json({"error":"approved workspace request required"},403)
                project=STORE.one("SELECT * FROM projects WHERE id=?",(task["project_id"],))
                workspace=create_task_workspace(tid,project["path"])
                STORE.write("INSERT INTO workspaces VALUES (?,?,?,?,?,?)",(tid,task["project_id"],workspace["path"],workspace["branch"],"ready",now()))
                task_event(tid,"orchestrator","info",f"Isolated workspace created on branch {workspace['branch']}.")
                return self.json(workspace,201)
            if route.startswith("/api/tasks/") and route.endswith("/workspace-release-request"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,)); workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'",(tid,))
                if not task or not workspace: return self.json({"error":"ready workspace not found"},404)
                aid=uid(); detail=f"release:{tid}"
                STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(aid,task["project_id"],"critical",detail,"pending",now()))
                task_event(tid,"security","warning","Clean worktree release requires critical-operation approval; branch will be retained.")
                return self.json({"id":aid,"status":"pending","detail":detail},201)
            if route.startswith("/api/tasks/") and route.endswith("/workspace-release"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,)); workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'",(tid,))
                if not task or not workspace: return self.json({"error":"ready workspace not found"},404)
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind='critical' AND detail=? AND status='approved'",(task["project_id"],f"release:{tid}"))
                if not permitted: return self.json({"error":"approved workspace release request required"},403)
                project=STORE.one("SELECT * FROM projects WHERE id=?",(task["project_id"],)); release_task_workspace(project["path"],workspace["path"])
                STORE.write("UPDATE workspaces SET status='released' WHERE task_id=?",(tid,)); task_event(tid,"orchestrator","info",f"Clean workspace released; recovery branch {workspace['branch']} was retained.")
                return self.json({"task_id":tid,"status":"released","branch":workspace["branch"],"branch_preserved":True})
            if route.startswith("/api/tasks/") and route.endswith("/merge-request"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,)); workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='released'",(tid,))
                if not task or not workspace: return self.json({"error":"released workspace not found"},404)
                project=STORE.one("SELECT * FROM projects WHERE id=?",(task["project_id"],)); preview=merge_preview(project["path"],workspace["branch"])
                if not preview["can_merge"]:
                    task_event(tid, "security", "warning", f"Merge preview reported a conflict for {workspace['branch']} into {preview['target']}: {preview['detail']}")
                    return self.json(preview,409)
                aid=uid(); detail=approval_detail("merge", tid, target=preview["target"], target_oid=preview["target_oid"], branch=workspace["branch"], branch_oid=preview["branch_oid"])
                STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(aid,task["project_id"],"critical",detail,"pending",now()))
                task_event(tid,"security","warning",f"Merge into {preview['target']} requires critical-operation approval.")
                return self.json({"id":aid,"status":"pending",**preview},201)
            if route.startswith("/api/tasks/") and route.endswith("/merge"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,)); workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='released'",(tid,))
                if not task or not workspace: return self.json({"error":"released workspace not found"},404)
                project=STORE.one("SELECT * FROM projects WHERE id=?",(task["project_id"],)); preview=merge_preview(project["path"],workspace["branch"])
                detail=approval_detail("merge", tid, target=preview["target"], target_oid=preview["target_oid"], branch=workspace["branch"], branch_oid=preview["branch_oid"])
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind='critical' AND detail=? AND status='approved'",(task["project_id"],detail))
                if not permitted: return self.json({"error":"approved merge request for the current target required"},403)
                merge_recovery_branch(project["path"],workspace["branch"],preview["target"],preview["branch_oid"],preview["target_oid"])
                STORE.write("UPDATE workspaces SET status='merged' WHERE task_id=?",(tid,)); task_event(tid,"orchestrator","info",f"Recovery branch {workspace['branch']} merged into {preview['target']}; branch retained.")
                return self.json({"task_id":tid,"status":"merged","target":preview["target"],"branch":workspace["branch"],"branch_preserved":True})
            if route.startswith("/api/tasks/") and route.endswith("/branch-delete-request"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,)); workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='merged'",(tid,))
                if not task or not workspace: return self.json({"error":"merged recovery branch not found"},404)
                project=STORE.one("SELECT * FROM projects WHERE id=?",(task["project_id"],)); branch_oid=ref_oid(project["path"],workspace["branch"])
                aid=uid(); detail=approval_detail("branch-delete", tid, branch=workspace["branch"], branch_oid=branch_oid)
                STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(aid,task["project_id"],"critical",detail,"pending",now()))
                task_event(tid,"security","warning",f"Deleting recovery branch {workspace['branch']} requires critical-operation approval.")
                return self.json({"id":aid,"status":"pending","branch":workspace["branch"]},201)
            if route.startswith("/api/tasks/") and route.endswith("/branch-delete"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,)); workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='merged'",(tid,))
                if not task or not workspace: return self.json({"error":"merged recovery branch not found"},404)
                project=STORE.one("SELECT * FROM projects WHERE id=?",(task["project_id"],)); branch_oid=ref_oid(project["path"],workspace["branch"])
                detail=approval_detail("branch-delete", tid, branch=workspace["branch"], branch_oid=branch_oid)
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind='critical' AND detail=? AND status='approved'",(task["project_id"],detail))
                if not permitted: return self.json({"error":"approved recovery-branch deletion request required"},403)
                delete_merged_branch(project["path"],workspace["branch"],branch_oid)
                STORE.write("UPDATE workspaces SET status='complete' WHERE task_id=?",(tid,)); task_event(tid,"orchestrator","info","Merged recovery branch deleted after critical approval.")
                return self.json({"task_id":tid,"status":"complete","branch_deleted":True})
            if route.startswith("/api/tasks/") and route.endswith("/agent/round/request"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'",(tid,))
                if not workspace: return self.json({"error":"ready task workspace required"},403)
                if task["status"] in {"completed","cancelled"}: return self.json({"error":f"task is {task['status']}"},409)
                provider=provider_row(data.get("provider_id"))
                if not provider: return self.json({"error":"provider not found"},404)
                if not provider["enabled"]: return self.json({"error":"provider is disabled"},400)
                budget=round_budget_error(tid)
                if budget: return self.json({"error":budget,"limits":round_limits(tid)},409)
                limits=round_limits(tid); number=limits["next_round"]
                prompt=validate_provider_prompt(build_round_prompt(task,workspace,str(data.get("prompt") or ""),decoded_rounds(tid)))
                kind=provider_approval_kind(provider); detail=round_invocation_detail(tid,provider,prompt,number); aid=uid()
                STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(aid,task["project_id"],kind,detail,"pending",now()))
                prompt_sha=json.loads(detail)["refs"]["prompt_sha256"]
                task_event(tid,"security","warning",f"Round {number} provider request on {provider['model']} requires {kind} approval.")
                return self.json({"round":number,"approval_id":aid,"status":"pending","kind":kind,"provider_id":provider["id"],"prompt_sha256":prompt_sha,"limits":limits},201)
            if route.startswith("/api/tasks/") and route.endswith("/agent/round/plan"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'",(tid,))
                if not workspace: return self.json({"error":"ready task workspace required"},403)
                if task["status"] in {"completed","cancelled"}: return self.json({"error":f"task is {task['status']}"},409)
                provider=provider_row(data.get("provider_id"))
                if not provider: return self.json({"error":"provider not found"},404)
                if not provider["enabled"]: return self.json({"error":"provider is disabled"},400)
                budget=round_budget_error(tid)
                if budget: return self.json({"error":budget,"limits":round_limits(tid)},409)
                limits=round_limits(tid); number=limits["next_round"]
                prompt=validate_provider_prompt(build_round_prompt(task,workspace,str(data.get("prompt") or ""),decoded_rounds(tid)))
                kind=provider_approval_kind(provider); detail=round_invocation_detail(tid,provider,prompt,number)
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind=? AND detail=? AND status='approved'",(task["project_id"],kind,detail))
                if not permitted: return self.json({"error":f"approved {kind} request for this exact round {number} prompt required"},403)
                result=invoke_provider(provider,prompt,active_provider_transport(provider)); result["text"]=redacted(result["text"])
                prompt_sha=json.loads(detail)["refs"]["prompt_sha256"]; iid=uid()
                repeated=STORE.one("SELECT id FROM invocations WHERE task_id=? AND response=? LIMIT 1",(tid,result["text"]))
                if repeated:
                    task_event(tid,"security","warning",f"Round {number} repeated an identical provider response; it was refused.")
                    return self.json({"error":"provider repeated an identical response; request a genuinely different next step","round":number},409)
                STORE.write("INSERT INTO invocations VALUES (?,?,?,?,?,?)",(iid,tid,provider["id"],prompt_sha,result["text"],now()))
                parsed=tools.parse_round_proposal(result["text"])
                if parsed["status"]=="continue":
                    operations=tools.bind_hashes(Path(workspace["path"]), parsed["operations"])
                    digest=tools.proposal_digest(tid, workspace["branch"], operations)
                    if STORE.one("SELECT id FROM rounds WHERE task_id=? AND proposal_digest=? AND status!='cancelled'",(tid,digest)):
                        task_event(tid,"security","warning",f"Round {number} repeated an already-seen proposal; it was refused.")
                        return self.json({"error":"identical proposal already reviewed for this task; request a genuinely different change","digest":digest},409)
                    proposal_id=uid(); proposal_approval=uid()
                    STORE.write("INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?)",(proposal_id,tid,workspace["branch"],workspace["path"],parsed["summary"],json.dumps(operations),digest,"pending",None,now()))
                    STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(proposal_approval,task["project_id"],"modify",round_proposal_detail(tid,number,workspace,digest,prompt_sha),"pending",now()))
                    rid=insert_round(tid,number,provider,prompt_sha,"awaiting-approval",parsed["summary"],proposal_id,digest,proposal_approval,operations)
                    STORE.write("UPDATE tasks SET status='iterating', updated_at=? WHERE id=?",(now(),tid))
                    task_event(tid,"planner","info",f"Round {number} proposes {len(operations)} operation(s); digest {digest[:12]}.")
                    task_event(tid,"security","warning",f"Round {number} changes require approval of this exact proposal digest.")
                    return self.json({"round_id":rid,"round":number,"status":"awaiting-approval","proposal_id":proposal_id,"digest":digest,"summary":parsed["summary"],"operations":operations,"approval_id":proposal_approval,"invocation_id":iid,"limits":limits},201)
                rounds=decoded_rounds(tid)
                if parsed["status"]=="complete":
                    proven,reason=tools.completion_evidence(rounds)
                    if not proven:
                        rid=insert_round(tid,number,provider,prompt_sha,"rejected-completion",parsed["summary"],error=reason)
                        task_event(tid,"reviewer","warning",f"Round {number} claimed completion without evidence: {reason}.")
                        return self.json({"error":f"completion rejected: {reason}","round_id":rid,"round":number,"status":"rejected-completion","limits":round_limits(tid)},409)
                    rid=insert_round(tid,number,provider,prompt_sha,"complete",parsed["summary"])
                    STORE.write("UPDATE tasks SET status='completed', updated_at=? WHERE id=?",(now(),tid))
                    task_event(tid,"reviewer","info",f"Round {number} completed the task with verified evidence: {reason}.")
                    return self.json({"round_id":rid,"round":number,"status":"complete","summary":parsed["summary"],"evidence":reason,"report":task_report(tid)},201)
                rid=insert_round(tid,number,provider,prompt_sha,parsed["status"],parsed["summary"])
                STORE.write("UPDATE tasks SET status=?, updated_at=? WHERE id=?",(parsed["status"],now(),tid))
                task_event(tid,"orchestrator","warning",f"Round {number} is {parsed['status']}: {parsed['summary'][:300]}")
                return self.json({"round_id":rid,"round":number,"status":parsed["status"],"summary":parsed["summary"],"limits":round_limits(tid)},201)
            if route.startswith("/api/tasks/") and route.endswith("/agent/round/execute"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                round_row=STORE.one("SELECT * FROM rounds WHERE task_id=? AND status='awaiting-approval' ORDER BY round_number DESC LIMIT 1",(tid,))
                if not round_row: return self.json({"error":"no round awaiting approval"},404)
                proposal=STORE.one("SELECT * FROM proposals WHERE id=? AND status='pending'",(round_row["proposal_id"],))
                if not proposal: return self.json({"error":"round proposal is not pending"},409)
                operations=json.loads(proposal["operations"]); digest=tools.proposal_digest(tid, proposal["workspace_branch"], operations)
                if digest != proposal["digest"] or digest != round_row["proposal_digest"]:
                    return self.json({"error":"Stored proposal was modified after review; request a new round"},409)
                workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'",(tid,))
                if not workspace or workspace["branch"] != proposal["workspace_branch"] or workspace["path"] != proposal["workspace_path"]:
                    return self.json({"error":"Workspace changed since approval; request a new round"},409)
                detail=round_proposal_detail(tid, round_row["round_number"], workspace, digest, round_row["prompt_sha256"])
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind='modify' AND detail=? AND status='approved'",(task["project_id"],detail))
                if not permitted: return self.json({"error":"approved round proposal for this exact digest and workspace required"},403)
                claim=STORE.conn.execute("UPDATE proposals SET status='executing' WHERE id=? AND status='pending'",(proposal["id"],))
                if claim.rowcount != 1: STORE.conn.rollback(); return self.json({"error":"Proposal is already being executed"},409)
                round_claim=STORE.conn.execute("UPDATE rounds SET status='executing', updated_at=? WHERE id=? AND status='awaiting-approval'",(now(),round_row["id"]))
                STORE.conn.commit()
                if round_claim.rowcount != 1: return self.json({"error":"Round is already being executed"},409)
                outcome=tools.execute_operations(Path(workspace["path"]), operations, runner=lambda command,timeout: execute_in_workspace(workspace["path"],command,timeout))
                feedback=tools.round_feedback(Path(workspace["path"]), operations, outcome["operations"], redact=redacted)
                hard_failures=[r for r in outcome["operations"] if r["status"]=="error" and r["tool"]!="run_tests"]
                if hard_failures:
                    final="failed"; error="; ".join(feedback["errors"])[:400] or "operation failed"
                elif feedback["tests_ran"] and feedback["test_exit_code"]==0 and outcome["ok"]:
                    final="passed"; error=None
                else:
                    final="failed-checks"; error="round ran no passing test command" if not feedback["tests_ran"] else f"test command exited {feedback['test_exit_code']}"
                STORE.write("UPDATE proposals SET status=?, results=? WHERE id=?",("executed" if outcome["ok"] else "failed",json.dumps(outcome["operations"]),proposal["id"]))
                STORE.write("UPDATE rounds SET status=?, results=?, test_result=?, error=?, updated_at=? WHERE id=?",(final,json.dumps(outcome["operations"]),json.dumps(feedback),error,now(),round_row["id"]))
                limits=round_limits(tid)
                task_status="ready-to-complete" if final=="passed" else ("needs-another-round" if limits["remaining"]>0 else "exhausted")
                STORE.write("UPDATE tasks SET status=?, updated_at=? WHERE id=?",(task_status,now(),tid))
                for entry in outcome["operations"]:
                    task_event(tid,"executor","info" if entry["status"]=="ok" else "warning",f"Round {round_row['round_number']} tool {entry['tool']} #{entry['index']+1}: {entry['status']}{(' — '+entry['error']) if entry.get('error') else ''}.")
                task_event(tid,"testing","info" if final=="passed" else "warning",f"Round {round_row['round_number']} {final}.")
                return self.json({"round_id":round_row["id"],"round":round_row["round_number"],"status":final,"ok":outcome["ok"],"results":outcome["operations"],"feedback":feedback,"task_status":task_status,"limits":limits})
            if route.startswith("/api/tasks/") and route.endswith("/agent/round/cancel"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                active=STORE.one("SELECT * FROM rounds WHERE task_id=? AND status IN ('awaiting-approval','executing') ORDER BY round_number DESC LIMIT 1",(tid,))
                if not active: return self.json({"error":"no active round to cancel"},404)
                STORE.write("UPDATE rounds SET status='cancelled', updated_at=? WHERE id=? AND status IN ('awaiting-approval','executing')",(now(),active["id"]))
                STORE.write("UPDATE proposals SET status='cancelled' WHERE id=? AND status IN ('pending','executing')",(active["proposal_id"],))
                STORE.write("UPDATE tasks SET status='cancelled', updated_at=? WHERE id=?",(now(),tid))
                task_event(tid,"orchestrator","warning",f"Round {active['round_number']} cancelled; its pending approval cannot execute.")
                return self.json({"round":active["round_number"],"status":"cancelled","task_status":"cancelled"})
            if route.startswith("/api/tasks/") and route.endswith("/agent/request"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'",(tid,))
                if not workspace: return self.json({"error":"ready task workspace required"},403)
                provider=provider_row(data.get("provider_id"))
                if not provider: return self.json({"error":"provider not found"},404)
                if not provider["enabled"]: return self.json({"error":"provider is disabled"},400)
                prompt=validate_provider_prompt(build_agent_prompt(task, workspace, str(data.get("prompt") or "")))
                kind=provider_approval_kind(provider); detail=provider_invocation_detail(tid,provider,prompt); aid=uid()
                STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(aid,task["project_id"],kind,detail,"pending",now()))
                task_event(tid,"security","warning",f"Agent proposal generation on {provider['model']} requires {kind} approval.")
                return self.json({"approval_id":aid,"status":"pending","kind":kind,"provider_id":provider["id"],"cloud_allowed":bool(provider["cloud_allowed"]),"detail":json.loads(detail)},201)
            if route.startswith("/api/tasks/") and route.endswith("/agent/plan"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'",(tid,))
                if not workspace: return self.json({"error":"ready task workspace required"},403)
                provider=provider_row(data.get("provider_id"))
                if not provider: return self.json({"error":"provider not found"},404)
                if not provider["enabled"]: return self.json({"error":"provider is disabled"},400)
                prompt=validate_provider_prompt(build_agent_prompt(task, workspace, str(data.get("prompt") or "")))
                kind=provider_approval_kind(provider); detail=provider_invocation_detail(tid,provider,prompt)
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind=? AND detail=? AND status='approved'",(task["project_id"],kind,detail))
                if not permitted: return self.json({"error":f"approved {kind} request for this exact workspace, provider, and prompt required"},403)
                result=invoke_provider(provider,prompt,active_provider_transport(provider)); result["text"]=redacted(result["text"])
                digest_prompt=json.loads(detail)["refs"]["prompt_sha256"]; iid=uid()
                STORE.write("INSERT INTO invocations VALUES (?,?,?,?,?,?)",(iid,tid,provider["id"],digest_prompt,result["text"],now()))
                parsed=tools.parse_proposal(result["text"])
                operations=tools.bind_hashes(Path(workspace["path"]), parsed["operations"])
                digest=tools.proposal_digest(tid, workspace["branch"], operations); proposal_id=uid()
                STORE.write("INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?)",(proposal_id,tid,workspace["branch"],workspace["path"],parsed["summary"],json.dumps(operations),digest,"pending",None,now()))
                approval_detail_value=approval_detail("agent-proposal", tid, workspace=workspace["branch"], workspace_path=workspace["path"], proposal=digest)
                approval_id=uid(); STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(approval_id,task["project_id"],"modify",approval_detail_value,"pending",now()))
                task_event(tid,"planner","info",f"Agent proposal contains {len(operations)} operation(s); summary digest {digest[:12]}.")
                task_event(tid,"security","warning","Proposed file modifications and test commands require explicit approval before they run.")
                return self.json({"proposal_id":proposal_id,"digest":digest,"summary":parsed["summary"],"operations":operations,"approval_id":approval_id,"invocation_id":iid},201)
            if route.startswith("/api/tasks/") and route.endswith("/agent/execute"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                proposal=STORE.one("SELECT * FROM proposals WHERE task_id=? AND status='pending' ORDER BY created_at DESC LIMIT 1",(tid,))
                if not proposal: return self.json({"error":"pending agent proposal not found"},404)
                operations=json.loads(proposal["operations"]); digest=tools.proposal_digest(tid, proposal["workspace_branch"], operations)
                if digest != proposal["digest"]: return self.json({"error":"Stored proposal was modified after review; request a new proposal"},409)
                workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'",(tid,))
                if not workspace or workspace["branch"] != proposal["workspace_branch"] or workspace["path"] != proposal["workspace_path"]:
                    return self.json({"error":"Workspace changed since approval; request a new proposal"},409)
                detail=approval_detail("agent-proposal", tid, workspace=proposal["workspace_branch"], workspace_path=proposal["workspace_path"], proposal=digest)
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind='modify' AND detail=? AND status='approved'",(task["project_id"],detail))
                if not permitted: return self.json({"error":"approved agent proposal for this exact workspace and digest required"},403)
                claim=STORE.conn.execute("UPDATE proposals SET status='executing' WHERE id=? AND status='pending'",(proposal["id"],)); STORE.conn.commit()
                if claim.rowcount != 1: return self.json({"error":"Proposal is already being executed"},409)
                outcome=tools.execute_operations(Path(workspace["path"]), operations, runner=lambda command,timeout: execute_in_workspace(workspace["path"],command,timeout))
                final="executed" if outcome["ok"] else "failed"
                STORE.write("UPDATE proposals SET status=?, results=? WHERE id=?",(final,json.dumps(outcome["operations"]),proposal["id"]))
                for entry in outcome["operations"]:
                    task_event(tid,"executor","info" if entry["status"]=="ok" else "warning",f"Tool {entry['tool']} #{entry['index']+1}: {entry['status']}{(' — '+entry['error']) if entry.get('error') else ''}.")
                return self.json({"proposal_id":proposal["id"],"status":final,"ok":outcome["ok"],"results":outcome["operations"]})
            if route.startswith("/api/tasks/") and route.endswith("/provider-request"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                provider=STORE.one("SELECT id,kind,endpoint,model,cloud_allowed,enabled FROM providers WHERE id=?",(data.get("provider_id"),))
                if not provider: return self.json({"error":"provider not found"},404)
                if not provider["enabled"]: return self.json({"error":"provider is disabled"},400)
                prompt=validate_provider_prompt(data.get("prompt"))
                kind=provider_approval_kind(provider); detail=provider_invocation_detail(tid,provider,prompt); aid=uid()
                STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(aid,task["project_id"],kind,detail,"pending",now()))
                transmission="cloud transmission" if provider["cloud_allowed"] else "loopback invocation"
                task_event(tid,"security","warning",f"Approved {transmission} on model {provider['model']} requires {kind} approval; prompt stays local until then.")
                return self.json({"id":aid,"status":"pending","kind":kind,"cloud_allowed":bool(provider["cloud_allowed"]),"detail":json.loads(detail)},201)
            if route.startswith("/api/tasks/") and route.endswith("/invoke"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,))
                if not task: return self.json({"error":"task not found"},404)
                provider=STORE.one("SELECT id,kind,endpoint,model,cloud_allowed,enabled,secret_ref FROM providers WHERE id=?",(data.get("provider_id"),))
                if not provider: return self.json({"error":"provider not found"},404)
                if not provider["enabled"]: return self.json({"error":"provider is disabled"},400)
                prompt=validate_provider_prompt(data.get("prompt")); kind=provider_approval_kind(provider)
                detail=provider_invocation_detail(tid,provider,prompt)
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind=? AND detail=? AND status='approved'",(task["project_id"],kind,detail))
                if not permitted: return self.json({"error":f"approved {kind} request for this exact provider, endpoint, model, and prompt required"},403)
                result=invoke_provider(provider,prompt,active_provider_transport(provider)); result["text"]=redacted(result["text"])
                digest=json.loads(detail)["refs"]["prompt_sha256"]; iid=uid()
                STORE.write("INSERT INTO invocations VALUES (?,?,?,?,?,?)",(iid,tid,provider["id"],digest,result["text"],now()))
                transmission="cloud" if provider["cloud_allowed"] else "loopback"
                task_event(tid,"provider","info",f"Approved {transmission} provider invocation completed on model {provider['model']} for prompt sha256 {digest[:12]}.")
                return self.json({"id":iid,"task_id":tid,"provider_id":provider["id"],"model":result["model"],"text":result["text"],"prompt_sha256":digest,"cloud_allowed":bool(provider["cloud_allowed"])})
            if route.startswith("/api/tasks/") and route.endswith("/execution-request"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,)); command=str(data.get("command","")).strip()
                if not task: return self.json({"error":"task not found"},404)
                parse_command(command); aid=uid(); detail=f"execute:{tid}:{command}"
                STORE.write("INSERT INTO approvals VALUES (?,?,?,?,?,?)",(aid,task["project_id"],"execute",detail,"pending",now()))
                return self.json({"id":aid,"status":"pending","detail":detail},201)
            if route.startswith("/api/tasks/") and route.endswith("/execute"):
                tid=route.split("/")[3]; task=STORE.one("SELECT * FROM tasks WHERE id=?",(tid,)); command=str(data.get("command","")).strip()
                if not task: return self.json({"error":"task not found"},404)
                workspace=STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'",(tid,))
                if not workspace: return self.json({"error":"ready task workspace required"},403)
                permitted=STORE.one("SELECT * FROM approvals WHERE project_id=? AND kind='execute' AND detail=? AND status='approved'",(task["project_id"],f"execute:{tid}:{command}"))
                if not permitted: return self.json({"error":"approved exact command request required"},403)
                result=execute_in_workspace(workspace["path"],command,data.get("timeout",120)); eid=uid()
                STORE.write("INSERT INTO executions VALUES (?,?,?,?,?,?)",(eid,tid,json.dumps(result["argv"]),result["exit_code"],result["output"],now()))
                task_event(tid,"executor","info",f"Approved command completed with exit code {result['exit_code']}.")
                return self.json({"id":eid,**result})
            return self.json({"error":"not found"},404)
        except (ValueError, sqlite3.IntegrityError) as e: return self.json({"error":str(e)},400)
        except json.JSONDecodeError: return self.json({"error":"invalid JSON"},400)
    def do_PATCH(self):
        route=self.route()
        if route.startswith("/api/approvals/"):
            aid=route.split("/")[3]; data=self.body(); status=data.get("status")
            if status not in {"approved","rejected"}: return self.json({"error":"status must be approved or rejected"},400)
            approval=STORE.one("SELECT * FROM approvals WHERE id=?",(aid,))
            if not approval: return self.json({"error":"approval not found"},404)
            if approval["status"] != "pending": return self.json({"error":"approval has already been decided"},409)
            STORE.write("UPDATE approvals SET status=? WHERE id=?",(status,aid)); return self.json({"id":aid,"status":status})
        return self.json({"error":"not found"},404)

if __name__ == "__main__":
    host=os.getenv("PERSONAL_CODEX_HOST","127.0.0.1"); port=int(os.getenv("PERSONAL_CODEX_PORT","8787"))
    print(f"Personal Codex control plane: http://{host}:{port}")
    ThreadingHTTPServer((host,port),App).serve_forever()
