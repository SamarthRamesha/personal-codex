"""Preparation contracts and read-only preflight; no Docker or remote changes."""
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch
from scripts import deployment_preflight as preflight
from app import mac_worker

ROOT=Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)
        self.settings={'PC_ROOT':str(self.base/'PersonalCodex'),'PC_UID':str(os.getuid()),'PC_GID':str(os.getgid()),'PC_IMAGE':'sha256:'+'a'*64,'PC_ORIGIN':'https://synthetic.private.ts.net'}
    def layout(self):
        root=Path(self.settings['PC_ROOT']);root.mkdir(mode=0o700)
        for path in (root/'data',root/'data'/'projects',root/'secrets'):path.mkdir(mode=0o700)
        for name,value in [('owner-token','a'*48),('worker-token','b'*48)]:
            path=root/'secrets'/name;path.write_text(value);path.chmod(0o600)
        return root
    def test_manifest_is_nonroot_bounded_and_mounts_only_dedicated_resources(self):
        s=json.loads((ROOT/'deploy/compose.review.json').read_text())['services']['backend']
        self.assertTrue(s['read_only']);self.assertEqual(s['cap_drop'],['ALL']);self.assertEqual(s['security_opt'],['no-new-privileges:true'])
        self.assertNotIn('ports',s);self.assertNotIn('privileged',s);self.assertEqual(s['network_mode'],'host')
        self.assertEqual(s['pull_policy'],'never');self.assertEqual(s['pids_limit'],128);self.assertEqual(s['mem_limit'],'512m')
        self.assertEqual(s['environment']['PERSONAL_CODEX_EXECUTION_MODE'],'disabled')
        for mount in s['volumes']:
            self.assertTrue(mount['source'].startswith('${PC_ROOT:'))
            self.assertFalse(mount['bind']['create_host_path'])
            self.assertNotIn('docker.sock',mount['source'])
        self.assertEqual(s['logging']['options'],{'max-size':'2m','max-file':'3'})
        agent=plistlib.loads((ROOT/'deploy/local.personalcodex.mac-worker.plist.example').read_bytes())
        self.assertIn('--log-file',agent['ProgramArguments']);self.assertIn('qwen2.5-coder:14b',agent['ProgramArguments'])
    def test_unsafe_paths_images_identity_and_origin_refused(self):
        for key,value in [('PC_ROOT','/DATA/Backup'),('PC_ROOT',str(self.base/'other')),('PC_UID','0'),('PC_GID','0'),('PC_IMAGE','latest'),('PC_ORIGIN','http://host.ts.net'),('PC_ORIGIN','https://backend.example.ts.net')]:
            with self.assertRaises(ValueError):preflight.validate_settings({**self.settings,key:value},self.base)
        root,_,_=preflight.validate_settings(self.settings,self.base);self.assertEqual(root,self.base/'PersonalCodex')
    def test_preflight_reads_only_named_layout_without_mutating_it(self):
        root=self.layout();before={p.relative_to(root):p.stat().st_mtime_ns for p in root.rglob('*')}
        usage=type('Usage',(),{'free':250*preflight.GB})()
        with patch.object(preflight.shutil,'disk_usage',return_value=usage):
            self.assertFalse(preflight.inspect_layout(root,os.getuid(),os.getgid())['mutations'])
        self.assertEqual(before,{p.relative_to(root):p.stat().st_mtime_ns for p in root.rglob('*')})
    def test_symlinks_shared_credentials_permissions_and_capacity_refused(self):
        root=self.layout();token=root/'secrets'/'worker-token';original=token.read_text()
        token.write_text('a'*48)
        with self.assertRaisesRegex(ValueError,'distinct'):preflight.inspect_layout(root,os.getuid(),os.getgid())
        token.write_text(original);token.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'0600'):preflight.inspect_layout(root,os.getuid(),os.getgid())
        token.chmod(0o600)
        with patch.object(preflight.shutil,'disk_usage',return_value=type('Usage',(),{'free':204*preflight.GB})()):
            with self.assertRaisesRegex(ValueError,'205 GB'):preflight.inspect_layout(root,os.getuid(),os.getgid())
        link=self.base/'link';link.symlink_to(root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):preflight.inspect_layout(link,os.getuid(),os.getgid())
    def test_settings_never_evaluate_shell_or_accept_duplicates(self):
        path=self.base/'review.env'
        for value in ('PC_ROOT=$(touch /tmp/not-run)','PC_ROOT=a\nPC_ROOT=b','UNKNOWN=x'):
            path.write_text(value)
            with self.assertRaises(ValueError):preflight.read_settings(path)
        path.write_text('\n'.join(k+'='+v for k,v in self.settings.items()))
        self.assertEqual(preflight.read_settings(path),self.settings)
    def test_worker_logs_rotate_and_refuse_shared_or_symlink_files(self):
        private=self.base/'private';private.mkdir(mode=0o700)
        log=private/'worker.log';logger=mac_worker.worker_logger(log)
        for _ in range(4):logger.warning('synthetic harmless failure '+'.'*140000)
        self.assertLessEqual(len(list(private.glob('worker.log*'))),3)
        for item in private.iterdir():self.assertEqual(item.stat().st_mode&0o777,0o600)
        for handler in list(logger.handlers):handler.close();logger.removeHandler(handler)
        other=private/'other';other.write_text('untouched');other.chmod(0o600)
        link=private/'link';link.symlink_to(other)
        with self.assertRaises(OSError):mac_worker.worker_logger(link)
        private.chmod(0o755)
        with self.assertRaises(mac_worker.WorkerError):mac_worker.worker_logger(log)
        self.assertEqual(other.read_text(),'untouched')
