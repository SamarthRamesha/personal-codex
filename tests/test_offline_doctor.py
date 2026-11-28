"""The offline doctor must explain blockers without starting a service."""
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'offline_launcher', Path(__file__).resolve().parents[1] / 'scripts/offline_workstation.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def app_bundle(folder):
    app = Path(folder) / 'Personal Codex.app'
    binary = app / launcher.APP_BINARY
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text('#!/bin/sh\nexit 0\n')
    binary.chmod(0o700)
    return app


class DoctorTests(unittest.TestCase):
    def test_reports_blockers_without_claiming_readiness(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(launcher.sys, 'platform', 'linux'), \
                patch.object(launcher, 'listening', return_value=False):
            report = launcher.doctor(Path(folder) / 'profile', Path('/missing/Personal Codex.app'))
            checks = {check['check']: check for check in report['checks']}
            self.assertFalse(report['ready'])
            self.assertEqual(checks['platform']['status'], 'fail')
            self.assertEqual(checks['app-bundle']['status'], 'fail')
            self.assertIn('macOS', checks['platform']['remedy'])
            self.assertTrue(checks['data-directory']['remedy'] == '')
            self.assertIn('data-directory', [check['check'] for check in report['checks']])

    def test_ready_when_macos_serves_a_vetted_model_and_free_ports(self):
        with tempfile.TemporaryDirectory() as folder:
            app = app_bundle(folder)
            with patch.object(launcher.sys, 'platform', 'darwin'), \
                    patch.object(launcher.shutil, 'which', side_effect=lambda name: f'/usr/bin/{name}'), \
                    patch.object(launcher, 'listening', side_effect=lambda port: port == launcher.OLLAMA_PORT), \
                    patch.object(launcher, 'get_json', return_value={'models': [{'name': 'qwen3.5:9b'}]}):
                report = launcher.doctor(Path(folder) / 'profile', app, reuse_ollama=True)
            checks = {check['check']: check for check in report['checks']}
            self.assertTrue(report['ready'], report)
            self.assertEqual(checks['installed-models']['status'], 'ok')
            self.assertIn('qwen3.5:9b', checks['installed-models']['detail'])

    def test_unvetted_and_missing_models_are_distinguished(self):
        with tempfile.TemporaryDirectory() as folder:
            app = app_bundle(folder)
            with patch.object(launcher.sys, 'platform', 'darwin'), \
                    patch.object(launcher.shutil, 'which', side_effect=lambda name: f'/usr/bin/{name}'), \
                    patch.object(launcher, 'listening', side_effect=lambda port: port == launcher.OLLAMA_PORT), \
                    patch.object(launcher, 'get_json', return_value={'models': [{'name': 'llama3.2:3b'}]}):
                unvetted = launcher.doctor(Path(folder) / 'profile', app, 'llama3.2:3b', reuse_ollama=True)
                missing = launcher.doctor(Path(folder) / 'profile', app, 'qwen2.5-coder:14b', reuse_ollama=True)
            self.assertTrue(unvetted['ready'])
            self.assertIn('installed-models', unvetted['warnings'])
            self.assertFalse(missing['ready'])
            self.assertIn('installed-models', missing['failures'])

    def test_reuse_ollama_requires_a_listener(self):
        with tempfile.TemporaryDirectory() as folder:
            app = app_bundle(folder)
            with patch.object(launcher.sys, 'platform', 'darwin'), \
                    patch.object(launcher.shutil, 'which', side_effect=lambda name: f'/usr/bin/{name}'), \
                    patch.object(launcher, 'listening', return_value=False):
                report = launcher.doctor(Path(folder) / 'profile', app, reuse_ollama=True)
            self.assertFalse(report['ready'])
            self.assertIn('reuse-ollama', report['failures'])

    def test_json_report_is_parseable_and_sets_the_exit_status(self):
        report = {'ready': False, 'checks': [{'check': 'platform', 'status': 'fail',
                                              'detail': 'host reports linux', 'remedy': 'Run on macOS.'}],
                  'failures': ['platform'], 'warnings': []}
        output = io.StringIO()
        with redirect_stdout(output):
            status = launcher.print_doctor(report, as_json=True)
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue())['failures'], ['platform'])


if __name__ == '__main__':
    unittest.main()
