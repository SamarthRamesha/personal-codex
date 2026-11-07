"""Metadata checks are mocked/static, never represented as actual Docker enforcement."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from scripts import deployment_preflight,resolve_base_image

ROOT=Path(__file__).resolve().parents[1]


class DeploymentMetadataTests(unittest.TestCase):
    def sequence(self,**image_changes):
        info={'os':'linux','memory':True,'swap':True,'pids':True,'cpu':True,'cgroup':'2','security':['name=seccomp,profile=builtin','name=apparmor']}
        image={'id':'sha256:'+'a'*64,'bytes':150000000,'architecture':'amd64','os':'linux','volumes':None,'onbuild':None,**image_changes}
        return [(0,b'28.0.0'),(0,b'2.30.0'),(0,json.dumps(info).encode()),(0,json.dumps(image).encode())]
    def test_readonly_runtime_queries_are_scoped_and_report_no_service_verification(self):
        with patch('scripts.run_isolated_job.capture',side_effect=self.sequence()) as capture:
            result=deployment_preflight.inspect_runtime({'PC_IMAGE':'sha256:'+'a'*64})
            self.assertFalse(result['service_started']);self.assertFalse(result['container_enforcement_verified'])
            for call in capture.call_args_list:
                argv=call.args[0]
                self.assertEqual(argv[:3],['/usr/bin/docker','--host','unix:///var/run/docker.sock'])
                self.assertNotIn('pull',argv);self.assertNotIn('run',argv);self.assertNotIn('exec',argv);self.assertNotIn('sudo',argv)
    def test_implicit_volumes_oversized_wrong_platform_and_missing_caps_fail_closed(self):
        for change in ({'volumes':{'/host-data':{}}},{'onbuild':['RUN unsafe']},{'architecture':'arm64'},{'bytes':1024**3}):
            with patch('scripts.run_isolated_job.capture',side_effect=self.sequence(**change)):
                with self.assertRaises(ValueError):deployment_preflight.inspect_runtime({'PC_IMAGE':'sha256:'+'a'*64})
        values=self.sequence();info=json.loads(values[2][1]);info['pids']=False;values[2]=(0,json.dumps(info).encode())
        with patch('scripts.run_isolated_job.capture',side_effect=values):
            with self.assertRaises(ValueError):deployment_preflight.inspect_runtime({'PC_IMAGE':'sha256:'+'a'*64})
    def test_public_base_lock_has_exact_digest_size_and_no_download_claim(self):
        lock=json.loads((ROOT/'deploy/base-image.lock.json').read_text())
        self.assertRegex(lock['base_image'],r'^docker.io/library/python@sha256:[a-f0-9]{64}$')
        self.assertEqual(lock['platform'],'linux/amd64');self.assertTrue(lock['metadata_only']);self.assertFalse(lock['layers_downloaded']);self.assertFalse(lock['image_built'])
        self.assertEqual(sum(item['bytes'] for item in lock['layers']),lock['compressed_layer_bytes'])
        with self.assertRaisesRegex(ValueError,'digest'):resolve_base_image.document(b'{}','sha256:'+'0'*64)
    def test_credentials_directory_mount_is_readonly_and_rotation_tracks_new_inodes(self):
        service=json.loads((ROOT/'deploy/compose.review.json').read_text())['services']['backend']
        credentials=[mount for mount in service['volumes'] if mount['target']=='/run/secrets']
        self.assertEqual(len(credentials),1);self.assertTrue(credentials[0]['read_only']);self.assertFalse(credentials[0]['bind']['create_host_path'])
        self.assertEqual(service['environment']['PERSONAL_CODEX_STORAGE_ENFORCE'],'1')
        self.assertEqual(service['environment']['PERSONAL_CODEX_DB_MAX_MIB'],'1024')
