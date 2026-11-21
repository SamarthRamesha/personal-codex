"""Lifecycle scope changes must fail before a model, worker or mutation starts."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import security, server, task_backend


class TaskBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / "project"
        (self.source / ".git").mkdir(parents=True)
        self.old = server.DATA, server.DB_PATH, server.STORE, server.AUTH
        server.DATA, server.DB_PATH = self.root / "data", self.root / "data/test.db"
        server.STORE = server.Store()
        self.addCleanup(self.restore)
        server.AUTH = security.OwnerAuth("synthetic-task-owner-000000000000000")
        self.env = patch.dict(os.environ, {"PERSONAL_CODEX_INFERENCE_POLICY": "offline",
                              "PERSONAL_CODEX_EXECUTION_MODE": "development", "PERSONAL_CODEX_PROJECT_ROOTS": str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.project = server.uid()
        server.STORE.write("INSERT INTO projects VALUES (?,?,?,?)", (self.project, "synthetic", str(self.source), 1))
        server.seed_offline_providers()
        self.provider = "offline-ollama-qwen3.5:9b"
        self.git = patch.object(server.project_review, "git_read", return_value=SimpleNamespace(returncode=0, stdout=b"a"*40))
        self.git_mock = self.git.start()
        self.addCleanup(self.git.stop)
        self.start = patch.object(server.project_agent, "start", return_value={"status": "running"})
        self.start_mock = self.start.start()
        self.addCleanup(self.start.stop)
        self.invoke = patch.object(server, "invoke_provider", side_effect=AssertionError("planning must not invoke a model"))
        self.invoke.start()
        self.addCleanup(self.invoke.stop)
        self.backend = server.task_service()
        self.request = {"project_id": self.project, "prompt": "Build a synthetic Python calculator", "attachments": [],
                        "provider_id": self.provider, "rounds": 4, "confirm": True}

    def restore(self):
        server.STORE.close()
        server.DATA, server.DB_PATH, server.STORE, server.AUTH = self.old

    def task(self):
        identifier = server.uid()
        server.STORE.write("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)",
                           (identifier, self.project, "Synthetic coding request", "pending", "[]", 1, 1))
        return identifier

    def seed_full_run(self, plan, status="interrupted"):
        value = json.loads(plan.payload)
        task = value["task"]
        server.STORE.write("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)",
                           (task["id"], task["project_id"], task["prompt"], status, "[]", 1, 1))
        server.STORE.write("INSERT INTO full_tasks VALUES (?,?,NULL,NULL)", (task["id"], json.dumps(value["scope"])))
        server.STORE.write("INSERT INTO autonomous_runs VALUES (?,?,?,?,?,?,?,?,?)",
                           (task["id"], self.provider, "full-task", status, 1, 4, "Synthetic interrupted run", "[]", 1))
        return task["id"]

    def test_plan_is_read_only_detached_and_does_not_log_its_prompt(self):
        plan = self.backend.plan_task(self.request)
        self.request["prompt"] = "Changed caller object"
        self.request["attachments"].append("not-selected")
        self.assertNotIn("synthetic Python", repr(plan))
        self.assertEqual(json.loads(plan.payload)["scope"]["attachments"], [])
        self.assertIn("synthetic Python", json.loads(plan.payload)["task"]["prompt"])
        for table in ("tasks", "full_tasks", "autonomous_runs", "invocations", "workspaces"):
            self.assertEqual(server.STORE.one(f"SELECT COUNT(*) AS n FROM {table}")["n"], 0)
        self.start_mock.assert_not_called()

    def test_execute_requires_a_separate_exact_boolean_confirmation(self):
        plan = self.backend.plan_task(self.request)
        for confirmation in (False, 1, "true", None):
            with self.subTest(confirmation=confirmation), self.assertRaises(ValueError):
                self.backend.execute_task(plan, confirm=confirmation)
        self.start_mock.assert_not_called()

    def test_execute_uses_the_existing_engine_with_the_bound_scope(self):
        plan = self.backend.plan_task(self.request)
        value = json.loads(plan.payload)
        result = self.backend.execute_task(plan, confirm=True)
        self.assertEqual(result["task_id"], value["task"]["id"])
        args, options = self.start_mock.call_args
        self.assertIs(args[0], server)
        self.assertEqual(args[3:5], ("full-task", 4))
        self.assertEqual(options["scope"]["baseline"], "a"*40)
        self.assertEqual(options["scope"]["provider_identity"]["model"], "qwen3.5:9b")

    def test_provider_drift_is_refused_before_execution(self):
        plan = self.backend.plan_task(self.request)
        server.STORE.write("UPDATE providers SET model='qwen2.5-coder:14b' WHERE id=?", (self.provider,))
        with self.assertRaisesRegex(ValueError, "provider changed"):
            self.backend.execute_task(plan, confirm=True)
        self.start_mock.assert_not_called()

    def test_destination_replacement_is_refused_before_execution(self):
        plan = self.backend.plan_task(self.request)
        self.source.rename(self.root / "original-project")
        (self.source / ".git").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "destination directory changed"):
            self.backend.execute_task(plan, confirm=True)
        self.start_mock.assert_not_called()

    def test_git_revision_drift_is_refused_before_execution(self):
        plan = self.backend.plan_task(self.request)
        self.git_mock.return_value.stdout = b"b"*40
        with self.assertRaisesRegex(ValueError, "Git revision changed"):
            self.backend.execute_task(plan, confirm=True)
        self.start_mock.assert_not_called()

    def test_disabled_execution_still_blocks_the_common_backend(self):
        with patch.dict(os.environ, {"PERSONAL_CODEX_EXECUTION_MODE": "disabled"}):
            with self.assertRaises(server.ExecutionDisabledError):
                self.backend.plan_task(self.request)
        self.git_mock.assert_not_called()

    def test_worker_only_deployment_cannot_enter_native_coding(self):
        with patch.dict(os.environ, {"PERSONAL_CODEX_INFERENCE_POLICY": "worker-only"}):
            with self.assertRaises(server.ExecutionDisabledError):
                self.backend.plan_task(self.request)
        self.start_mock.assert_not_called()

    def test_owner_authentication_remains_required(self):
        server.AUTH = security.OwnerAuth()
        with self.assertRaises(server.ExecutionDisabledError):
            self.backend.plan_task(self.request)

    def test_unknown_permission_fields_and_boolean_budgets_are_refused(self):
        for request in ({**self.request, "allow_network": True}, {**self.request, "rounds": True},
                        {**self.request, "seconds": True}, {**self.request, "confirm": False}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.backend.plan_task(request)
        self.start_mock.assert_not_called()

    def test_unknown_project_and_foreign_attachments_fail_before_task_creation(self):
        with self.assertRaises(LookupError):
            self.backend.plan_task({**self.request, "project_id": server.uid()})
        with self.assertRaises(ValueError):
            self.backend.plan_task({**self.request, "attachments": [server.uid()]})
        self.start_mock.assert_not_called()

    def test_inspection_is_available_when_execution_is_disabled(self):
        identifier = self.task()
        with patch.dict(os.environ, {"PERSONAL_CODEX_EXECUTION_MODE": "disabled"}):
            self.assertEqual(self.backend.inspect_task(identifier)["status"], "idle")
        self.start_mock.assert_not_called()

    def test_full_resume_preserves_scope_and_refuses_provider_switch(self):
        identifier = self.seed_full_run(self.backend.plan_task(self.request))
        self.backend.resume_task(identifier, {"confirm": True})
        self.assertEqual(self.start_mock.call_args.args[3:5], ("full-task", 4))
        self.assertNotIn("scope", self.start_mock.call_args.kwargs)
        self.start_mock.reset_mock()
        server.STORE.write("UPDATE providers SET model='qwen2.5-coder:14b' WHERE id=?", (self.provider,))
        with self.assertRaisesRegex(ValueError, "provider changed"):
            self.backend.resume_task(identifier, {"confirm": True})
        self.start_mock.assert_not_called()

    def test_resume_requires_confirmation_and_original_destination(self):
        identifier = self.seed_full_run(self.backend.plan_task(self.request))
        with self.assertRaises(ValueError):
            self.backend.resume_task(identifier, {"confirm": False})
        self.git_mock.return_value.stdout = b"b"*40
        with self.assertRaisesRegex(ValueError, "destination changed"):
            self.backend.resume_task(identifier, {"confirm": True})
        self.start_mock.assert_not_called()

    def test_already_submitted_plan_cannot_create_or_replay_a_task(self):
        plan = self.backend.plan_task(self.request)
        identifier = self.seed_full_run(plan)
        self.start.stop()  # Exercise the actual claim guard; it must not start a thread.
        with self.assertRaisesRegex(ValueError, "already submitted"):
            self.backend.execute_task(plan, confirm=True)
        self.assertFalse(server.project_agent.running(identifier))
        self.assertEqual(server.STORE.one("SELECT COUNT(*) AS n FROM tasks")["n"], 1)

    def test_command_workflow_uses_the_same_plan_execute_contract(self):
        identifier = self.task()
        request = {"provider_id": self.provider, "command": "python3 -m unittest discover -s tests -v",
                   "rounds": 2, "confirm": True}
        result = self.backend.execute_task(self.backend.plan_task(request, task_id=identifier), confirm=True)
        self.assertEqual(result["task_id"], identifier)
        self.assertIsNone(self.start_mock.call_args.kwargs["scope"])
        self.assertEqual(self.start_mock.call_args.args[3], request["command"])


if __name__ == "__main__":
    unittest.main()
