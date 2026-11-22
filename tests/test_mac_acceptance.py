"""The acceptance summariser must never turn a non-pass into a pass.

These run on Linux because that is where the verdict logic lives; they say nothing about macOS
windowed behaviour.
"""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mac_acceptance", ROOT / "scripts/mac_acceptance.py")
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


def check(name, passed, detail=None):
    return {"name": name, "passed": passed, **({"detail": detail} if detail else {})}


class SummaryTests(unittest.TestCase):
    def test_a_full_pass_is_verified(self):
        report = {"status": "passed", "actual_ui_exercised": True,
                  "checks": [check("native_scrollbar_result", True), check("window_identity_refused", True)]}
        summary = acceptance.summarize(report)
        self.assertEqual(summary["verdict"], acceptance.VERIFIED)
        self.assertEqual((summary["total"], summary["passed"], summary["failures"]), (2, 2, []))
        self.assertIn("All 2", summary["headline"])

    def test_one_failure_is_named_not_summarised_away(self):
        report = {"status": "needs_review", "checks": [
            check("prepare_is_read_only", True),
            check("native_scrollbar_result", False, "no editable scrollbar with a value was observed")]}
        summary = acceptance.summarize(report)
        self.assertEqual(summary["verdict"], acceptance.NOT_VERIFIED)
        self.assertEqual(summary["failures"], [{"name": "native_scrollbar_result",
                                                "detail": "no editable scrollbar with a value was observed"}])
        self.assertIn("native_scrollbar_result", summary["headline"])

    def test_a_pass_with_no_listed_checks_is_not_verification(self):
        summary = acceptance.summarize({"status": "passed", "checks": []})
        self.assertEqual(summary["verdict"], acceptance.NOT_VERIFIED)
        self.assertIn("no checks", summary["headline"])

    def test_an_unexpected_status_is_not_a_pass(self):
        summary = acceptance.summarize({"status": "needs_review", "checks": [check("a", True)]})
        self.assertEqual(summary["verdict"], acceptance.NOT_VERIFIED)

    def test_permission_is_reported_as_the_owner_action_it_is(self):
        summary = acceptance.summarize({"status": "permission_required", "actual_ui_exercised": False})
        self.assertEqual(summary["verdict"], acceptance.PERMISSION)
        self.assertIn("Accessibility", summary["headline"])
        self.assertEqual(acceptance.EXIT[summary["verdict"]], 2)

    def test_a_stopped_run_reports_the_stage(self):
        summary = acceptance.summarize({"status": "failed", "stage": "native_scrollbar",
                                        "error": "AutomationError.targetChanged", "checks": []})
        self.assertEqual(summary["verdict"], acceptance.STOPPED)
        self.assertIn("native_scrollbar", summary["headline"])
        self.assertIn("targetChanged", summary["headline"])

    def test_unreadable_input_is_never_a_pass(self):
        for value in (None, [], "passed", 42):
            summary = acceptance.summarize(value)
            self.assertEqual(summary["verdict"], acceptance.UNREADABLE)
            self.assertIn("nothing is verified", summary["headline"])

    def test_a_pass_that_claims_no_real_ui_is_not_verified(self):
        summary = acceptance.summarize({"status": "passed", "checks": [check("a", True)]})
        self.assertEqual(summary["verdict"], acceptance.NOT_VERIFIED)
        self.assertIn("real UI", summary["headline"])

    def test_a_passing_run_states_what_it_never_exercised(self):
        summary = acceptance.summarize({"status": "passed", "actual_ui_exercised": True,
                                        "capture_requested": False, "browser_exercised": False,
                                        "checks": [check("a", True)]})
        self.assertEqual(summary["verdict"], acceptance.VERIFIED)
        self.assertEqual(summary["not_exercised"], [
            "capture/OCR (re-run with --capture once Screen Recording is granted)",
            "browser workflow (owner-run, runbook stage 7)"])
        self.assertIn("NOT EXERCISED capture/OCR", acceptance.render({**summary, "_checks": ["a"]}))

    def test_unknown_fields_are_not_echoed(self):
        summary = acceptance.summarize({"status": "needs_review", "checks": [
            {"name": "selected_window_isolation", "passed": False, "value": "SYNTHETIC-SECRET"}]})
        self.assertNotIn("SYNTHETIC-SECRET", json.dumps(summary))


class CommandTests(unittest.TestCase):
    def test_report_mode_returns_the_verdict_as_exit_status(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            saved = Path(folder) / "kept.json"
            report.write_text(json.dumps({"status": "passed", "actual_ui_exercised": True,
                                          "checks": [check("a", True)]}))
            output = io.StringIO()
            with redirect_stdout(output):
                code = acceptance.main(["--report", str(report), "--save", str(saved)])
            self.assertEqual(code, 0)
            self.assertIn("PASS a", output.getvalue())
            self.assertEqual(json.loads(saved.read_text())["status"], "passed")

            report.write_text(json.dumps({"status": "needs_review", "checks": [check("a", False, "why")]}))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(acceptance.main(["--report", str(report)]), 1)

    def test_a_missing_candidate_helper_exits_four_and_saves_nothing(self):
        # The documented contract says a helper that never ran is exit 4, not a failing check list.
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / "no-helper"
            saved = Path(folder) / "saved.json"
            output = io.StringIO()
            with redirect_stdout(output):
                code = acceptance.main(["--run", "--helper", str(missing), "--save", str(saved)])
            self.assertEqual(code, acceptance.EXIT[acceptance.COULD_NOT_RUN])
            self.assertEqual(code, 4)
            self.assertIn("build_mac_automation.py", output.getvalue())
            self.assertFalse(saved.exists(), "a run that never happened must not leave a saved report")

    def test_the_script_never_grants_permission(self):
        source = (ROOT / "scripts/mac_acceptance.py").read_text()
        for forbidden in ("tccutil", "request_accessibility", "AXIsProcessTrustedWithOptions",
                          "codesign", "--request", "sudo"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
