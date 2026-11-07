"""Prototype policy and local negative proof. Linux runtime acceptance remains separate."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import isolation,secure_files

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('isolated_executor',ROOT/'scripts/isolated_executor.py');executor=importlib.util.module_from_spec(spec);spec.loader.exec_module(executor)


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve();self.addCleanup(self.tmp.cleanup)
        self.source=self.base/'source';self.source.mkdir();(self.source/'test_example.py').write_text('import unittest\n')
        self.argv=['python3','-m','unittest','discover','-s','tests','-v']
    def request(self):return isolation.request(self.source,self.argv)
    def test_contract_carries_source_in_stdin_without_any_host_mount_or_network(self):
        value=self.request();argv=isolation.docker_argv(value,'sha256:'+'a'*64,1000,1000,'/run/user/1000/docker.sock')
        self.assertEqual(argv[argv.index('--network')+1],'none');self.assertIn('--read-only',argv)
        self.assertNotIn('--mount',argv);self.assertNotIn('--volume',argv);self.assertNotIn('--privileged',argv)
        self.assertNotIn('--publish',argv);self.assertNotIn('--env-file',argv);self.assertNotIn('--device',argv)
        self.assertEqual(argv[argv.index('--user')+1],'1000:1000');self.assertEqual(argv[argv.index('--cap-drop')+1],'ALL')
        self.assertIn('apparmor=docker-default',argv);self.assertIn('no-new-privileges:true',argv)
        self.assertEqual(argv[argv.index('--memory')+1],argv[argv.index('--memory-swap')+1]);self.assertIn('--cgroupns',argv)
        self.assertEqual(argv[argv.index('--pull')+1],'never');self.assertEqual(argv[argv.index('--log-driver')+1],'none')
        self.assertEqual(isolation.validate(value)['test_example.py'],b'import unittest\n')
    def test_command_or_content_changes_break_review_digest(self):
        value=self.request();value['argv'].append('-q')
        with self.assertRaisesRegex(ValueError,'digest'):isolation.validate(value)
        value=self.request();value['files']['test_example.py']='YWx0ZXJlZA=='
        with self.assertRaisesRegex(ValueError,'digest'):isolation.validate(value)
    def test_unknown_fields_root_identity_mutable_images_and_remote_daemons_rejected(self):
        value=self.request()
        with self.assertRaises(ValueError):isolation.validate({**value,'docker_args':['--privileged']})
        for image,uid,socket in [('latest',1000,'/run/docker.sock'),('sha256:'+'a'*64,0,'/run/docker.sock'),('sha256:'+'a'*64,1000,'tcp://remote:2375')]:
            with self.assertRaises(ValueError):isolation.docker_argv(value,image,uid,1000,socket)
        for command in (['sh','-c','echo unsafe'],['docker','run','--privileged'],['python3','-c','print(1)']):
            with self.assertRaises(ValueError):isolation.request(self.source,command)
    def test_secret_named_input_is_rejected_before_content_read_and_git_is_excluded(self):
        (self.source/'.git').mkdir();(self.source/'.git/config').write_text('not mounted')
        self.assertNotIn('.git/config',isolation.validate(self.request()))
        (self.source/'.env').write_text('synthetic credential')
        with self.assertRaisesRegex(ValueError,'Excluded snapshot'):self.request()
    def test_symlinks_hardlinks_and_special_files_never_enter_snapshot(self):
        outside=self.base/'unrelated';outside.write_text('private synthetic')
        link=self.source/'link';link.symlink_to(outside)
        with self.assertRaises(ValueError):self.request()
        link.unlink();os.link(outside,link)
        with self.assertRaises(ValueError):self.request()
        link.unlink();os.mkfifo(link)
        with self.assertRaises(ValueError):self.request()
        self.assertEqual(outside.read_text(),'private synthetic')
    def test_budgets_path_traversal_and_file_directory_collisions_fail_closed(self):
        with self.assertRaises(ValueError):secure_files.read_tree(self.source,max_bytes=1)
        value=self.request();value['files']['../outside']='eA=='
        with self.assertRaises(ValueError):isolation.validate(value)
        for name in ('/absolute','a/../b','a//b','a\\b'):
            with self.assertRaises(ValueError):secure_files.canonical_name(name)
        value=self.request();value['files']['test_example.py/child']='eA=='
        with self.assertRaisesRegex(ValueError,'collision'):isolation.validate(value)
    def test_missing_any_os_control_prevents_process_spawn(self):
        with patch.object(executor.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'OS isolation'):executor.execute(self.request(),{'seccomp':True,'network':False})
            spawn.assert_not_called()
    def test_local_macos_is_not_claimed_as_linux_runtime_proof(self):
        with patch('platform.system',return_value='Darwin'):
            self.assertEqual(isolation.runtime_checks(),{'linux':False})

    def test_broad_family_and_other_application_scopes_rejected_before_inventory(self):
        with patch.object(secure_files,'read_tree') as read:
            for path in ('/DATA','/DATA/Backup','/DATA/Gallery/photos','/DATA/AppData/other','/','/DATA/AppData'):
                with self.assertRaises(ValueError):isolation.request(Path(path),self.argv)
            read.assert_not_called()

    def test_apparmor_complain_mode_is_not_accepted_as_enforcement(self):
        for label,expected in [('docker-default (enforce)',True),('docker-default (complain)',False),('unconfined',False)]:
            with patch('platform.system',return_value='Linux'),patch.object(isolation.os,'listdir',return_value=['lo']),patch.object(Path,'read_text',lambda path:label if str(path)=='/proc/self/attr/current' else ''):
                self.assertEqual(isolation.runtime_checks()['apparmor'],expected)


spec2=importlib.util.spec_from_file_location('run_isolated_job',ROOT/'scripts/run_isolated_job.py');supervisor=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(supervisor)


class SupervisorTests(unittest.TestCase):
    def test_host_capture_bounds_output_independently_of_container_claims(self):
        import sys
        with self.assertRaisesRegex(supervisor.ExecutionError,'output budget'):
            supervisor.capture([sys.executable,'-c','import sys; sys.stdout.write("x"*300000)'],timeout=3)
    def test_host_capture_bounds_silent_process_total_duration(self):
        import sys,time
        started=time.monotonic()
        with self.assertRaisesRegex(supervisor.ExecutionError,'deadline'):
            supervisor.capture([sys.executable,'-c','import time; time.sleep(3)'],timeout=.15)
        self.assertLess(time.monotonic()-started,1.5)
    def test_macos_refuses_execution_before_docker_or_state_mutation(self):
        with patch.object(supervisor.platform,'system',return_value='Darwin'),patch.object(supervisor,'capture') as capture:
            with self.assertRaisesRegex(supervisor.ExecutionError,'Linux'):supervisor.run_reviewed(Path('/not-read'),'x','latest',1,1,'/run/docker.sock')
            capture.assert_not_called()
    def test_failed_probe_never_runs_source_and_ambiguous_claim_cannot_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory).resolve();parent.chmod(0o700);source=parent/'source';source.mkdir();(source/'a.py').write_text('synthetic')
            value=isolation.request(source,['python3','-m','unittest']);path=parent/'request.json';secure_files.write_new(path,isolation.canonical(value))
            with patch.object(supervisor.platform,'system',return_value='Linux'),patch.object(supervisor,'capture',side_effect=[(0,b'null'),(2,b'{"verified":false,"checks":{"seccomp":false}}')]) as capture,patch.object(supervisor.subprocess,'run'):
                with self.assertRaisesRegex(supervisor.ExecutionError,'probe failed'):supervisor.run_reviewed(path,value['request_sha256'],'sha256:'+'a'*64,1000,1000,'/run/docker.sock')
                self.assertEqual(capture.call_count,2)
                with self.assertRaises(FileExistsError):supervisor.run_reviewed(path,value['request_sha256'],'sha256:'+'a'*64,1000,1000,'/run/docker.sock')
            self.assertTrue((parent/'started.json').exists());self.assertFalse((parent/'result.json').exists())
