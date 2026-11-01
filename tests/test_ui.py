"""Browser-free dashboard regression tests.

These check the static dashboard against the control-plane routes without needing a browser or DOM:
element ids referenced by the script must exist, every action button must be wired, every API path
used by the script must be routed by the server, and no remote asset or inline secret is embedded.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
SERVER = (ROOT / "app" / "server.py").read_text(encoding="utf-8")


def js_ids() -> set[str]:
    return set(re.findall(r"""\$\(['"]#([A-Za-z0-9_-]+)['"]\)""", JS))


def html_ids() -> set[str]:
    return set(re.findall(r'id="([A-Za-z0-9_-]+)"', HTML))


def html_button_ids() -> set[str]:
    return set(re.findall(r'<button[^>]*id="([A-Za-z0-9_-]+)"', HTML))


class DashboardContractTests(unittest.TestCase):
    def test_every_scripted_element_exists_in_markup(self):
        missing = sorted(js_ids() - html_ids())
        self.assertEqual(missing, [], f"app.js references missing element ids: {missing}")

    def test_every_markup_button_is_wired(self):
        handlers = set(re.findall(r"""\$\(['"]#([A-Za-z0-9_-]+)['"]\)\.onclick""", JS))
        unwired = sorted(html_button_ids() - handlers)
        self.assertEqual(unwired, [], f"buttons without a script handler: {unwired}")

    def test_every_api_path_in_script_is_routed_by_server(self):
        paths = set(re.findall(r"(/api/[A-Za-z-]+)", JS))
        unrouted = sorted(path for path in paths if path not in SERVER)
        self.assertEqual(unrouted, [], f"script calls unrouted API paths: {unrouted}")

    def test_provider_invocation_controls_are_present_and_routed(self):
        for element in ("provider-select", "provider-prompt", "request-provider-invoke", "invoke-provider", "task-invocations"):
            self.assertIn(element, HTML)
        for route in ("provider-request", "/invoke", "/invocations"):
            self.assertIn(route, SERVER)
            self.assertIn(route, JS)

    def test_approval_controls_cover_every_gated_action(self):
        for element in ("request-workspace", "create-workspace", "request-command", "run-command",
                        "request-release", "release-workspace", "preview-merge", "request-merge",
                        "merge-branch", "request-branch-delete", "delete-branch"):
            self.assertIn(element, HTML)
            self.assertIn(element, JS)

    def test_round_history_controls_are_present_and_routed(self):
        for element in ("request-agent-round", "plan-agent-round", "execute-agent-round",
                        "cancel-agent-round", "agent-rounds", "agent-report"):
            self.assertIn(element, HTML)
            self.assertIn(element, JS)
        for route in ("/agent/rounds", "/agent/report", "/round/request", "/round/plan",
                      "/round/execute", "/round/cancel"):
            self.assertIn(route, SERVER)
            self.assertIn(route, JS)

    def test_dashboard_loads_only_local_assets_and_no_stored_secrets(self):
        self.assertFalse(re.search(r'(?:src|href)="https?://', HTML), "dashboard must not load remote assets")
        self.assertIn('src="/app.js"', HTML)
        self.assertIn('href="/style.css"', HTML)
        self.assertTrue((ROOT / "web" / "app.js").is_file())
        self.assertTrue((ROOT / "web" / "style.css").is_file())
        for storage in ("localStorage", "sessionStorage", "document.cookie"):
            self.assertNotIn(storage, JS, "the dashboard must not persist secrets in browser storage")


if __name__ == "__main__":
    unittest.main()
