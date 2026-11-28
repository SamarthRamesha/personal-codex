"""Synthetic dependency proposals and real sandboxed npm installs; no owner files."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import tarfile
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from app import dependencies, server, security


def tarball():
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, data in {'package/package.json': b'{"name":"synthetic-package","version":"1.0.0","main":"index.js"}',
                           'package/index.js': b'module.exports = 42;'} .items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.old = server.DATA, server.DB_PATH, server.STORE
        server.DATA = self.root / 'data'
        server.DB_PATH = server.DATA / 'test.db'
        self.store = server.Store()
        self.addCleanup(self.restore)
        self.workspace = server.DATA / 'workspaces' / 'fixture'
        self.workspace.mkdir(parents=True)
        self.store.write('INSERT INTO workspaces VALUES (?,?,?,?,?,?)', ('task', 'project', str(self.workspace), 'branch', 'ready', 1))
        self.host = SimpleNamespace(STORE=self.store, DATA=server.DATA, AUTH=security.OwnerAuth('synthetic-owner-token-00000000000000000'),
            network_policy=SimpleNamespace(offline_only=lambda: True), require_execution=lambda: None,
            project_agent=SimpleNamespace(running=lambda task: False), safe_workspace_path=lambda row: Path(row['path']),
            uid=server.uid, now=server.now, STOPPING=threading.Event(), redacted=server.redacted,
            child_limits=server.child_limits, terminate_process_group=server.terminate_process_group)
        self.installer = dependencies.Installer(self.host)
        self.addCleanup(self.installer.close)
        self.raw = tarball()
        integrity = 'sha512-' + base64.b64encode(hashlib.sha512(self.raw).digest()).decode()
        self.lock = {'lockfileVersion': 3, 'packages': {
            '': {'name': 'fixture', 'version': '1.0.0', 'dependencies': {'synthetic-package': '1.0.0'}},
            'node_modules/synthetic-package': {'version': '1.0.0', 'resolved': 'https://registry.npmjs.org/synthetic-package/-/synthetic-package-1.0.0.tgz', 'integrity': integrity}}}
        self.manifest = {'name': 'fixture', 'version': '1.0.0', 'dependencies': {'synthetic-package': '1.0.0'},
                         'scripts': {'preinstall': 'node -e "require(\'fs\').writeFileSync(\'UNEXPECTED\',\'bad\')"'}}
        self.write()

    def restore(self):
        self.store.close()
        server.DATA, server.DB_PATH, server.STORE = self.old

    def write(self):
        (self.workspace / 'package.json').write_text(json.dumps(self.manifest))
        (self.workspace / 'package-lock.json').write_text(json.dumps(self.lock))

    def request(self, row):
        return {'id': row['id'], 'digest': row['digest'], 'confirm': True, 'confirm_network': True}

    def test_review_performs_no_download_or_command(self):
        with patch.object(dependencies, 'download', side_effect=AssertionError('network')), patch.object(dependencies.subprocess, 'Popen', side_effect=AssertionError('command')):
            row = self.installer.propose('task')
        self.assertEqual(row['status'], 'proposed')
        self.assertEqual(row['proposal']['network']['origin'], 'https://registry.npmjs.org')
        self.assertFalse((self.workspace / 'node_modules').exists())

    def test_changed_manifest_refuses_before_network(self):
        row = self.installer.propose('task')
        self.manifest['version'] = '2.0.0'
        self.write()
        with patch.object(dependencies, 'download', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.installer.execute('task', self.request(row))

    def test_confirmation_digest_and_expiry_required(self):
        row = self.installer.propose('task')
        for fields in ({'confirm_network': False}, {'digest': 'wrong'}, {'confirm': False}):
            with self.assertRaises(ValueError):
                self.installer.execute('task', {**self.request(row), **fields})
        self.store.write('UPDATE dependency_jobs SET expires_at=0 WHERE id=?', (row['id'],))
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.installer.execute('task', self.request(row))

    def test_existing_tree_is_preserved(self):
        (self.workspace / 'node_modules').mkdir()
        marker = self.workspace / 'node_modules' / 'keep'
        marker.write_text('unchanged')
        with self.assertRaisesRegex(ValueError, 'preserved'):
            self.installer.propose('task')
        self.assertEqual(marker.read_text(), 'unchanged')

    def test_external_registry_links_and_bad_integrity_refused(self):
        entry = self.lock['packages']['node_modules/synthetic-package']
        for fields in ({'resolved': 'https://example.com/p.tgz'}, {'resolved': 'http://registry.npmjs.org/p.tgz'},
                       {'resolved': 'https://registry.npmjs.org/p.tgz?token=bad'}, {'link': True}, {'integrity': 'sha512-bad'}):
            broken = json.loads(json.dumps(self.lock))
            broken['packages']['node_modules/synthetic-package'].update(fields)
            with self.assertRaises(ValueError):
                dependencies.package_plan({'package.json': json.dumps(self.manifest).encode(), 'package-lock.json': json.dumps(broken).encode()})
        self.assertTrue(entry['resolved'].startswith('https:'))

    def test_server_profile_cannot_install(self):
        self.host.network_policy.offline_only = lambda: False
        with self.assertRaisesRegex(ValueError, 'local offline'):
            self.installer.propose('task')

    def test_restart_marks_install_interrupted_without_replay(self):
        row = self.installer.propose('task')
        self.store.write("UPDATE dependency_jobs SET status='running' WHERE id=?", (row['id'],))
        self.store.recover_interrupted()
        self.assertEqual(self.installer.get('task')['status'], 'interrupted')
        with self.assertRaises(ValueError):
            self.installer.execute('task', self.request(row))

    def test_cancelled_download_never_publishes_and_claim_cannot_replay(self):
        row = self.installer.propose('task')
        entered = threading.Event()
        def slow(package, stopped):
            entered.set()
            while not stopped(): time.sleep(.01)
            raise ValueError('Installation cancelled')
        with patch.object(dependencies, 'download', slow):
            self.installer.execute('task', self.request(row))
            self.assertTrue(entered.wait(2))
            self.assertTrue(self.installer.cancel('task'))
            self.assertTrue(self.installer.close())
        self.assertEqual(self.installer.get('task')['status'], 'cancelled')
        self.assertFalse((self.workspace / 'node_modules').exists())
        with self.assertRaises(ValueError): self.installer.execute('task', self.request(row))

    def test_tampered_stored_proposal_is_refused(self):
        row = self.installer.propose('task')
        row['proposal']['writes'] = ['different authority']
        self.store.write('UPDATE dependency_jobs SET proposal=? WHERE id=?', (json.dumps(row['proposal']), row['id']))
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.installer.execute('task', self.request(row))

    def test_download_rejects_redirects_and_integrity_mismatch(self):
        package = dependencies.package_plan(dependencies.manifests(self.workspace))[0]
        for status, content in ((302, self.raw), (200, b'tampered')):
            response = SimpleNamespace(status=status, read=unittest.mock.Mock(side_effect=[content, b'']))
            connection = unittest.mock.Mock()
            connection.getresponse.return_value = response
            with patch.object(dependencies.http.client, 'HTTPSConnection', return_value=connection):
                with self.assertRaises(ValueError): dependencies.download(package, lambda: False)
            connection.close.assert_called_once()

    @unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS') == '1', 'requires explicitly enabled synthetic HTTP')
    def test_http_review_requires_owner_and_exact_confirmation(self):
        import http.client
        from http.server import ThreadingHTTPServer
        task = '00000000-0000-4000-8000-000000000001'
        self.store.write('UPDATE workspaces SET task_id=? WHERE task_id=?', (task, 'task'))
        old_auth, old_manager = server.AUTH, server._DEPENDENCIES
        server.STORE, server.AUTH, server._DEPENDENCIES = self.store, self.host.AUTH, self.installer
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.App)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        def call(suffix, body, token=True):
            connection = __import__('http.client', fromlist=['HTTPConnection']).HTTPConnection('127.0.0.1', http.server_port, timeout=5)
            headers = {'Content-Type': 'application/json'}
            if token: headers['Authorization'] = 'Bearer synthetic-owner-token-00000000000000000'
            connection.request('POST', f'/api/tasks/{task}/dependencies/{suffix}', json.dumps(body), headers)
            result = connection.getresponse()
            status, data = result.status, json.loads(result.read())
            connection.close()
            return status, data
        try:
            self.assertEqual(call('propose', {}, False)[0], 401)
            status, row = call('propose', {})
            self.assertEqual(status, 201)
            self.assertEqual(call('execute', {**self.request(row), 'confirm_network': False})[0], 400)
            self.assertEqual(call('propose', {'command': 'anything'})[0], 400)
            self.assertFalse((self.workspace / 'node_modules').exists())
        finally:
            http.shutdown();http.server_close();thread.join()
            server.AUTH, server._DEPENDENCIES = old_auth, old_manager

    @unittest.skipUnless(platform.system() == 'Darwin' and shutil.which('npm'), 'requires contained macOS npm')
    def test_real_offline_npm_installs_verified_tarball_without_scripts(self):
        row = self.installer.propose('task')
        before = dependencies.manifests(self.workspace)
        with patch.object(dependencies, 'download', return_value=(self.raw, 256)):
            self.installer.execute('task', self.request(row))
            for _ in range(600):
                if self.installer.get('task')['status'] != 'running': break
                time.sleep(.05)
            result = self.installer.get('task')
        self.assertEqual(result['status'], 'complete', result['output'])
        self.assertEqual((self.workspace / 'node_modules/synthetic-package/index.js').read_text(), 'module.exports = 42;')
        self.assertFalse((self.workspace / 'UNEXPECTED').exists())
        self.assertEqual(dependencies.manifests(self.workspace), before)
        with self.assertRaises(ValueError): self.installer.execute('task', self.request(row))


if __name__ == '__main__': unittest.main()
