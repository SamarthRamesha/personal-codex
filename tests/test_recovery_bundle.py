"""Real encrypted recovery over synthetic data; no personal paths or server runtime."""
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from app import recovery,runtime,secure_files,server
try:
    from cryptography.fernet import Fernet
except ImportError:Fernet=None


@unittest.skipIf(Fernet is None,'optional reviewed recovery cryptography dependency unavailable')
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve();self.addCleanup(self.tmp.cleanup)
        self.data=self.base/'data';self.data.mkdir(mode=0o700)
        with patch.object(server,'DATA',self.data),patch.object(server,'DB_PATH',self.data/'personal_codex.db'):
            self.store=server.Store()
        project=self.data/'projects'/'fixture';project.mkdir(parents=True)
        (project/'calculator.py').write_text('def add(a,b): return a+b\n')
        for command in (['git','init','--quiet'],['git','config','user.email','synthetic@example.invalid'],['git','config','user.name','Synthetic'],['git','add','.'],['git','commit','--quiet','-m','synthetic baseline']):
            subprocess.run(command,cwd=project,check=True,capture_output=True)
        workspace=self.data/'workspaces'/'task';workspace.mkdir(parents=True);(workspace/'change.txt').write_text('approved synthetic work')
        self.store.write('INSERT INTO projects VALUES (?,?,?,?)',('p','Fixture',str(project),1))
        self.store.write('INSERT INTO workspaces VALUES (?,?,?,?,?,?)',('task','p',str(workspace),'checkpoint','ready',1))
        self.store.write('INSERT INTO conversations (id,title,project_id,model,created_at,updated_at) VALUES (?,?,?,?,?,?)',('chat','private fixture conversation','p','fixture',1,1))
        self.store.write('INSERT INTO operations (id,task_id,round_id,round_number,op_index,tool,digest,status,started_at,applied) VALUES (?,?,?,?,?,?,?,?,?,?)',('op','task','round',1,1,'apply_patch','d'*64,'complete',1,1))
        self.store.close()
        self.key=self.base/'recovery-key';self.key.write_bytes(Fernet.generate_key());self.key.chmod(0o600)
        self.release=self.base/'release.zip'
        with zipfile.ZipFile(self.release,'w') as z:z.writestr('personal-codex/README.md','synthetic source release')
        self.output=self.base/'checkpoint.pcr';self.target=self.base/'restored'
        self.policy=patch.dict(os.environ,{'PERSONAL_CODEX_RESERVE_GB':'1','PERSONAL_CODEX_STORAGE_GB':'75'});self.policy.start();self.addCleanup(self.policy.stop)
    def checkpoint(self):return recovery.checkpoint(self.data,self.output,self.key,self.release,{'PC_ORIGIN':'https://synthetic.private.ts.net'})
    def test_encrypted_roundtrip_preserves_db_ledger_git_files_and_relocates_paths(self):
        before=(self.data/'personal_codex.db').read_bytes();result=self.checkpoint()
        self.assertTrue(result['encrypted']);self.assertEqual(self.output.stat().st_mode&0o777,0o600)
        self.assertNotIn(b'private fixture conversation',self.output.read_bytes());self.assertNotIn(b'synthetic source release',self.output.read_bytes())
        restored=recovery.restore(self.output,self.target,self.key)
        self.assertTrue(restored['execution_disabled']);self.assertFalse(restored['credentials_restored'])
        self.assertEqual((self.target/'data/projects/fixture/calculator.py').read_text(),'def add(a,b): return a+b\n')
        commit=subprocess.check_output(['git','-C',str(self.target/'data/projects/fixture'),'log','-1','--format=%s'],text=True).strip()
        self.assertEqual(commit,'synthetic baseline')
        db=sqlite3.connect(self.target/'data/personal_codex.db')
        try:
            self.assertEqual(db.execute('SELECT title FROM conversations').fetchone()[0],'private fixture conversation')
            self.assertEqual(db.execute('SELECT status,applied FROM operations').fetchone(),('complete',1))
            self.assertEqual(db.execute('SELECT path FROM projects').fetchone()[0],str(self.target/'data/projects/fixture'))
            self.assertEqual(db.execute('SELECT path FROM workspaces').fetchone()[0],str(self.target/'data/workspaces/task'))
        finally:db.close()
        self.assertEqual((self.data/'personal_codex.db').read_bytes(),before)
        self.assertTrue((self.target/'data/RECOVERY_LOCKED.json').exists());self.assertTrue((self.target/'data/RECOVERY_COMPLETE.json').exists())
        self.assertFalse((self.target/'secrets').exists())
        # Every restored path must keep the private modes checkpoint requires of its source, not
        # inherit 0o777 & ~umask from a parent-directory helper.
        for path in self.target.rglob('*'):
            info=path.lstat()
            self.assertEqual(stat.S_IMODE(info.st_mode),0o700 if stat.S_ISDIR(info.st_mode) else 0o600,str(path))
    def test_quiescence_no_overwrite_and_original_preservation(self):
        with runtime.InstanceLock(self.data):
            with self.assertRaisesRegex(ValueError,'already owns'):self.checkpoint()
        self.assertFalse(self.output.exists());self.checkpoint();before=self.output.read_bytes()
        with self.assertRaises(FileExistsError):self.checkpoint()
        self.assertEqual(before,self.output.read_bytes());recovery.restore(self.output,self.target,self.key)
        with self.assertRaises(FileExistsError):recovery.restore(self.output,self.target,self.key)
    def test_wrong_key_tamper_and_digest_mismatch_create_no_output(self):
        self.checkpoint();other=self.base/'wrong-key';other.write_bytes(Fernet.generate_key());other.chmod(0o600)
        with self.assertRaisesRegex(ValueError,'authentication'):recovery.restore(self.output,self.target,other)
        value=bytearray(self.output.read_bytes());value[len(value)//2]^=1;bad=self.base/'tampered';bad.write_bytes(value);bad.chmod(0o600)
        with self.assertRaisesRegex(ValueError,'authentication'):recovery.restore(bad,self.target,self.key)
        self.assertFalse(self.target.exists())
    def test_external_database_paths_and_symlinks_never_copied(self):
        outside=self.base/'unrelated';outside.mkdir();(outside/'untouched').write_text('private synthetic')
        connection=sqlite3.connect(self.data/'personal_codex.db');connection.execute('UPDATE projects SET path=?',(str(outside),));connection.commit();connection.close()
        with self.assertRaisesRegex(ValueError,'outside dedicated'):self.checkpoint()
        self.assertFalse(self.output.exists());self.assertEqual((outside/'untouched').read_text(),'private synthetic')
        (self.data/'projects'/'alias').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):secure_files.read_tree(self.data/'projects')
    def test_budget_protected_diagnostic_aliases_and_shared_key_refused(self):
        project=self.data/'projects/fixture'
        with self.assertRaises(ValueError):secure_files.read_tree(project,max_bytes=1)
        # Synthetic filename only; the user's diagnostic is never opened by any test.
        protected=project/'personal-codex-diagnostic.txt';protected.write_text('synthetic excluded')
        with self.assertRaisesRegex(ValueError,'Protected diagnostic'):self.checkpoint()
        protected.unlink()
        self.key.chmod(0o644)
        with self.assertRaises(ValueError):self.checkpoint()
        self.key.chmod(0o600);alias=project/'alias.py';os.link(project/'calculator.py',alias)
        with self.assertRaisesRegex(ValueError,'alias'):self.checkpoint()
    def test_secrets_and_existing_snapshots_are_excluded_without_reading(self):
        for name in ('secrets','backups'):
            folder=self.data/name;folder.mkdir();(folder/'private-placeholder').write_bytes(b'not part of recovery scope')
        self.checkpoint();entries,manifest=recovery.decode(self.output.read_bytes(),self.key)
        self.assertFalse(any('/secrets/' in name or '/backups/' in name for name in entries))
        self.assertEqual(manifest['configuration'],{'PC_ORIGIN':'https://synthetic.private.ts.net'})
        self.assertIn('excluded',manifest['credentials'])
    def test_partial_restore_retains_execution_lock_and_cannot_start_backend(self):
        self.checkpoint();real=secure_files.write_new
        def write(path,value):
            if Path(path).name=='calculator.py':raise OSError('synthetic write failure')
            return real(path,value)
        with patch.object(secure_files,'write_new',side_effect=write):
            with self.assertRaisesRegex(ValueError,'incomplete'):recovery.restore(self.output,self.target,self.key)
        self.assertTrue((self.target/'data/RECOVERY_LOCKED.json').exists());self.assertFalse((self.target/'data/RECOVERY_COMPLETE.json').exists())
        env={'PATH':os.environ.get('PATH',''),'PERSONAL_CODEX_DATA':str(self.target/'data'),'PERSONAL_CODEX_EXECUTION_MODE':'disabled'}
        result=subprocess.run([sys.executable,'-m','app.server'],cwd=server.ROOT,env=env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0);self.assertIn('Incomplete recovery',result.stderr)
    def test_complete_restore_still_refuses_development_execution(self):
        self.checkpoint();recovery.restore(self.output,self.target,self.key)
        env={'PATH':os.environ.get('PATH',''),'PERSONAL_CODEX_DATA':str(self.target/'data')}
        result=subprocess.run([sys.executable,'-m','app.server'],cwd=server.ROOT,env=env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0);self.assertIn('requires disabled execution',result.stderr)

    def test_restore_revokes_stale_approvals_and_interrupts_inflight_state(self):
        db=sqlite3.connect(self.data/'personal_codex.db')
        db.execute("INSERT INTO approvals (id,project_id,kind,detail,status,created_at) "
                   "VALUES ('approval','p','modify','old digest','approved',1)")
        db.execute("INSERT INTO messages (id,conversation_id,role,content,status,created_at,updated_at) VALUES ('mid','chat','assistant','partial','streaming',1,1)")
        db.execute("INSERT INTO inference_jobs (id,provider_id,model,prompt,prompt_sha256,status,deadline,created_at,updated_at) VALUES ('job','provider','fixture','must clear','digest','running',9999999999,1,1)")
        db.commit();db.close();self.checkpoint();result=recovery.restore(self.output,self.target,self.key)
        db=sqlite3.connect(self.target/'data/personal_codex.db')
        try:
            self.assertEqual(db.execute('SELECT status FROM approvals').fetchone()[0],'revoked')
            self.assertEqual(db.execute('SELECT status FROM messages').fetchone()[0],'stopped')
            self.assertEqual(db.execute('SELECT status,prompt,content,lease_hash FROM inference_jobs').fetchone(),('interrupted','','',None))
            self.assertEqual(db.execute('SELECT status FROM workspaces').fetchone()[0],'recovery-review')
            self.assertEqual(result['revoked_approvals'],1)
        finally:db.close()

    def test_authenticated_but_malicious_archive_paths_links_and_duplicates_are_refused(self):
        import tarfile
        for kind,name in [('file','../escape'),('symlink','data/projects/link'),('hardlink','data/projects/link'),('duplicate','data/projects/a')]:
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w') as archive:
                member=tarfile.TarInfo(name)
                if kind in {'symlink','hardlink'}:
                    member.type=tarfile.SYMTYPE if kind=='symlink' else tarfile.LNKTYPE;member.linkname='/unrelated';archive.addfile(member)
                else:
                    member.size=1;archive.addfile(member,io.BytesIO(b'x'))
                    if kind=='duplicate':archive.addfile(member,io.BytesIO(b'y'))
            payload=recovery.fernet(self.key).encrypt(buffer.getvalue())
            with self.assertRaises(ValueError):recovery.decode(payload,self.key)
        self.assertFalse((self.base/'escape').exists())
