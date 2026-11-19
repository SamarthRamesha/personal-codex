"""Versioned native coding lifecycle used by the existing authenticated routes.

This is a trusted in-process interface, not an authorization token or an engine
plugin loader. HTTP authentication and the caller's explicit confirmation remain
required. Planning reads metadata but never creates a task, invokes a model or
runs project code. Existing manual approval/round APIs keep their own boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Protocol


@dataclass(frozen=True)
class TaskPlan:
    # Immutable serialized values avoid sharing mutable request/scope dictionaries.
    payload: str = field(repr=False)


class TaskBackend(Protocol):
    def plan_task(self, request: dict, *, task_id: str | None = None) -> TaskPlan: ...
    def execute_task(self, plan: TaskPlan, *, confirm: bool) -> dict: ...
    def inspect_task(self, task_id: str) -> dict: ...
    def resume_task(self, task_id: str, request: dict) -> dict: ...


class NativeTaskBackend:
    VERSION = 1
    PROVIDER_FIELDS = ("id", "kind", "endpoint", "model", "secret_ref", "cloud_allowed")

    def __init__(self, host):
        self.host = host

    def _require(self, *, execution=True):
        if not self.host.network_policy.offline_only() or not self.host.AUTH.enabled:
            raise self.host.ExecutionDisabledError("The native coding backend requires authenticated offline mode")
        if execution:
            self.host.require_execution()

    def _provider(self, identifier):
        if not isinstance(identifier, str):
            raise ValueError("Select an installed local provider")
        row = self.host.provider_row(identifier)
        if not row or not row["enabled"]:
            raise ValueError("The authorized local provider is unavailable")
        self.host.network_policy.require_provider(row)
        return row

    def _identity(self, provider):
        return {key: provider.get(key) for key in self.PROVIDER_FIELDS}

    def _project(self, identifier):
        if not isinstance(identifier, str):
            raise ValueError("Select a project first")
        project = self.host.STORE.one("SELECT * FROM projects WHERE id=?", (identifier,))
        if not project:
            raise LookupError("Project not found")
        source = self.host.safe_project_path(project["path"])
        info = source.stat()
        return source, [info.st_dev, info.st_ino]

    def _baseline(self, source):
        if not (source / ".git").is_dir() or (source / ".git").is_symlink():
            raise ValueError("Select a Git repository with a regular .git directory")
        result = self.host.project_review.git_read(source, None, ["rev-parse", "HEAD"])
        if result.returncode:
            raise ValueError("The project needs an initial Git revision")
        baseline = result.stdout.decode("ascii").strip()
        if not re.fullmatch(r"[a-f0-9]{40,64}", baseline):
            raise ValueError("Could not determine the current Git revision")
        return baseline

    def plan_task(self, request: dict, *, task_id: str | None = None) -> TaskPlan:
        self._require()
        if not isinstance(request, dict):
            raise ValueError("Task request must be an object")
        scope = None
        if task_id is None:
            required = {"project_id", "prompt", "attachments", "provider_id", "rounds", "confirm"}
            if (not required.issubset(request) or set(request)-required-{"seconds"}
                    or request["confirm"] is not True):
                raise ValueError("Authorize one scoped full-task run and delivery to the selected repository")
            prompt = request["prompt"]
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > self.host.full_task.MAX_PROMPT:
                raise ValueError("Enter a complete task instruction of up to 8,000 characters")
            if type(request["rounds"]) is not int or not 2 <= request["rounds"] <= 12:
                raise ValueError("Choose between two and twelve full-task rounds")
            seconds = request.get("seconds", 540)
            if type(seconds) is not int or not 120 <= seconds <= 900:
                raise ValueError("Choose a time budget between two and fifteen minutes")
            source, identity = self._project(request["project_id"])
            baseline = self._baseline(source)
            references = self.host.full_task.attachment_inputs(self.host.STORE, request["project_id"], request["attachments"])
            scope = {"identity": identity, "baseline": baseline, "source": str(source), "seconds": seconds,
                     "attachments": references, "attachment_names": [item["name"] for item in references]}
            task_id, stamp = self.host.uid(), self.host.now()
            task = {"id": task_id, "project_id": request["project_id"], "prompt": prompt.strip(),
                    "created_at": stamp, "updated_at": stamp}
            command = "full-task"
        else:
            if set(request) != {"provider_id", "command", "rounds", "confirm"} or request["confirm"] is not True:
                raise ValueError("Confirm the workspace and exact validation command explicitly")
            command = request["command"]
            if not isinstance(command, str) or len(command) > 240:
                raise ValueError("Enter the exact local validation command")
            command = command.strip()
            self.host.local_runner.validate_command(self.host.parse_command(command))
            if type(request["rounds"]) is not int or not 1 <= request["rounds"] <= 6:
                raise ValueError("Choose between one and six coding rounds")
            task = self.host.STORE.one("SELECT * FROM tasks WHERE id=?", (task_id,))
            if not task:
                raise LookupError("Task not found")
            if self.host.full_task.fetch(self.host.STORE, task_id):
                raise ValueError("Resume a full task through its original full-task scope")
            source, identity = self._project(task["project_id"])
        provider = self._provider(request["provider_id"])
        if scope is not None:
            scope["provider_identity"] = self._identity(provider)
        payload = {"version": self.VERSION, "task": task, "provider": self._identity(provider), "command": command,
                   "rounds": request["rounds"], "source": str(source), "identity": identity, "scope": scope}
        return TaskPlan(json.dumps(payload, sort_keys=True))

    def execute_task(self, plan: TaskPlan, *, confirm: bool) -> dict:
        self._require()
        if confirm is not True or not isinstance(plan, TaskPlan):
            raise ValueError("Explicit task execution confirmation is required")
        value = json.loads(plan.payload)
        if value.get("version") != self.VERSION:
            raise ValueError("Unsupported task plan version")
        task = value["task"]
        provider = self._provider(value["provider"]["id"])
        if self._identity(provider) != value["provider"]:
            raise ValueError("The selected provider changed after planning; review a new plan")
        source, identity = self._project(task["project_id"])
        if identity != value["identity"] or str(source) != value["source"]:
            raise ValueError("The approved destination directory changed after planning")
        if value["scope"] is not None:
            if self._baseline(source) != value["scope"]["baseline"]:
                raise ValueError("The destination Git revision changed after planning")
        else:
            current = self.host.STORE.one("SELECT * FROM tasks WHERE id=?", (task["id"],))
            if not current or (current["project_id"], current["prompt"]) != (task["project_id"], task["prompt"]):
                raise ValueError("The task changed after planning")
        run = self.host.project_agent.start(self.host, task, provider, value["command"], value["rounds"], scope=value["scope"])
        return {"task_id": task["id"], "run": run}

    def inspect_task(self, task_id: str) -> dict:
        self._require(execution=False)
        if not self.host.STORE.one("SELECT id FROM tasks WHERE id=?", (task_id,)):
            raise LookupError("Task not found")
        run = self.host.project_agent.report(self.host.STORE, task_id)
        workspace = self.host.STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'", (task_id,))
        if workspace:
            root = self.host.safe_workspace_path(workspace)
            run["workspace"] = str(root)
            run["files"] = [entry["path"] for entry in self.host.tools.list_files(root, ".", 3, 100)["entries"]]
        return run

    def resume_task(self, task_id: str, request: dict) -> dict:
        self._require()
        previous = self.host.project_agent.report(self.host.STORE, task_id)
        spec = self.host.full_task.fetch(self.host.STORE, task_id)
        if spec is None:
            if set(request) == {"confirm"}:
                raise LookupError("Full task not found")
            if previous["status"] == "idle":
                raise ValueError("Start a task before requesting resume")
            return self.execute_task(self.plan_task(request, task_id=task_id), confirm=request.get("confirm"))["run"]
        if set(request) != {"confirm"} or request["confirm"] is not True:
            raise ValueError("Authorize another bounded attempt within the original scope")
        task = self.host.STORE.one("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not task or previous["status"] == "idle":
            raise LookupError("Full task not found")
        source, identity = self._project(task["project_id"])
        scope = spec["scope"]
        if (identity != scope["identity"] or str(source) != scope["source"]
                or self._baseline(source) != scope["baseline"]):
            raise ValueError("The approved destination changed; review the saved worktree before resuming")
        provider = self._provider(previous["provider_id"])
        # Old saved tasks predate this field; retain their existing provider-id
        # binding. New scopes additionally bind the exact provider descriptor.
        if scope.get("provider_identity", self._identity(provider)) != self._identity(provider):
            raise ValueError("The authorized provider changed; do not silently switch a resumed task")
        return self.host.project_agent.start(self.host, task, provider, "full-task", 4)
