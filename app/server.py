#!/usr/bin/env python3
"""Personal Codex local control plane. Standard-library only by design for v0."""
from __future__ import annotations

import json, os, re, resource, shlex, signal, sqlite3, subprocess, sys, tempfile, time, uuid
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

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

def approval_detail(action: str, task_id: str, **refs: str) -> str:
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
