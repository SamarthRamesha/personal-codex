#!/usr/bin/env python3
"""Personal Codex local control plane. Standard-library only by design for v0."""
from __future__ import annotations

import json, os, re, shlex, sqlite3, subprocess, sys, time, uuid
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB_PATH = DATA / "personal_codex.db"
WEB = ROOT / "web"
SECRET_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "credentials.json"}
ALLOWED_COMMANDS = {"git", "python", "python3", "pytest", "npm", "node", "cargo", "rustc", "go", "make"}

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
    return text[:200_000]

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

def execute_in_workspace(path: str, command: str, timeout=120) -> dict:
    argv=parse_command(command); root=Path(path).resolve()
    if not root.is_dir() or DATA.resolve() not in root.parents: raise ValueError("Execution must use a Personal Codex task workspace")
    env={"PATH":os.environ.get("PATH", ""), "HOME":str(root), "LANG":"C", "LC_ALL":"C"}
    try:
        result=subprocess.run(argv, cwd=root, env=env, text=True, capture_output=True, timeout=min(max(int(timeout),1),300), check=False)
        return {"argv":argv,"exit_code":result.returncode,"output":redacted((result.stdout or "")+(result.stderr or ""))}
    except subprocess.TimeoutExpired as e:
        return {"argv":argv,"exit_code":124,"output":redacted((e.stdout or "")+(e.stderr or "")+"\nTimed out.")}

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
        if route.startswith("/api/tasks/") and route.endswith("/workspace"):
            tid=route.split("/")[3]; return self.json(STORE.one("SELECT * FROM workspaces WHERE task_id=?",(tid,)) or {"task_id":tid,"status":"absent"})
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
                if not model: return self.json({"error":"model is required"},400)
                pid=uid(); STORE.write("INSERT INTO providers VALUES (?,?,?,?,?,?,?,?)",(pid,kind,endpoint,model,ref,int(bool(data.get("cloud_allowed"))),1,now()))
                return self.json({"id":pid,"note":"Only an environment-variable reference is stored; no secret value was accepted."},201)
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
            STORE.write("UPDATE approvals SET status=? WHERE id=?",(status,aid)); return self.json({"id":aid,"status":status})
        return self.json({"error":"not found"},404)

if __name__ == "__main__":
    host=os.getenv("PERSONAL_CODEX_HOST","127.0.0.1"); port=int(os.getenv("PERSONAL_CODEX_PORT","8787"))
    print(f"Personal Codex control plane: http://{host}:{port}")
    ThreadingHTTPServer((host,port),App).serve_forever()
