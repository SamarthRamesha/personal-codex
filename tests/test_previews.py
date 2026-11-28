"""Reviewed preview lifecycle against disposable Node HTTP servers."""
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from app import previews, server, security


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.old=server.DATA,server.DB_PATH,server.STORE
        server.DATA=self.root/'data';server.DB_PATH=server.DATA/'test.db'
        self.store=server.Store();self.addCleanup(self.restore)
        self.workspace=server.DATA/'workspaces/fixture';self.workspace.mkdir(parents=True)
        self.store.write('INSERT INTO workspaces VALUES (?,?,?,?,?,?)',('task','project',str(self.workspace),'branch','ready',1))
        self.host=SimpleNamespace(STORE=self.store,DATA=server.DATA,AUTH=security.OwnerAuth('synthetic-preview-owner-000000000000000'),
            network_policy=SimpleNamespace(offline_only=lambda:True),require_execution=lambda:None,
            safe_workspace_path=lambda row:Path(row['path']),project_agent=SimpleNamespace(running=lambda task:False),
            now=server.now,uid=server.uid,STOPPING=threading.Event(),redacted=server.redacted,terminate_process_group=server.terminate_process_group)
        self.service=previews.Previews(self.host);self.addCleanup(self.service.close)
        (self.workspace/'package.json').write_text(json.dumps({'scripts':{'dev':'node server.js'}}))
        (self.workspace/'server.js').write_text("require('http').createServer((q,r)=>{r.end('SYNTHETIC PREVIEW')}).listen(Number(process.env.PORT),process.env.HOST); console.log('preview listening');")
        self.port=self.free_port()

    def restore(self):
        self.store.close();server.DATA,server.DB_PATH,server.STORE=self.old

    @staticmethod
    def free_port():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

    @staticmethod
    def request(row):return {'id':row['id'],'digest':row['digest'],'confirm':True}

    def wait(self,status,timeout=15):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            row=self.service.get('task')
            if row['status']==status:return row
            if row['status'] in {'failed','stopped'} and status not in {'failed','stopped'}:
                self.fail(str(row))
            time.sleep(.1)
        self.fail(str(self.service.get('task')))

    def test_review_does_not_start_any_process(self):
        with patch.object(previews.subprocess,'Popen',side_effect=AssertionError('executed')):
            row=self.service.propose('task','dev',self.port)
        self.assertEqual(row['status'],'proposed');self.assertEqual(row['proposal']['url'],f'http://127.0.0.1:{self.port}')

    def test_modified_entry_and_expired_or_wrong_review_are_refused(self):
        row=self.service.propose('task','dev',self.port)
        with self.assertRaises(ValueError):self.service.execute('task',{**self.request(row),'confirm':False})
        with self.assertRaises(ValueError):self.service.execute('task',{**self.request(row),'digest':'wrong'})
        (self.workspace/'server.js').write_text('// changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.service.execute('task',self.request(row))
        self.store.write('UPDATE preview_jobs SET expires_at=0 WHERE id=?',(row['id'],))
        with self.assertRaisesRegex(ValueError,'expired'):self.service.execute('task',self.request(row))

    def test_unknown_commands_and_ports_are_refused(self):
        for port in (0,80,65536,True,'4000'):
            with self.assertRaises(ValueError):self.service.propose('task','dev',port)
        (self.workspace/'package.json').write_text(json.dumps({'scripts':{'dev':'node server.js && anything'}}))
        with self.assertRaises(ValueError):self.service.propose('task','dev',self.port)

    def test_restart_marks_active_preview_interrupted_without_replaying(self):
        row=self.service.propose('task','dev',self.port)
        self.store.write("UPDATE preview_jobs SET status='running' WHERE id=?",(row['id'],))
        self.store.recover_interrupted()
        self.assertEqual(self.service.get('task')['status'],'interrupted')
        with self.assertRaises(ValueError):self.service.execute('task',self.request(row))

    def test_existing_port_is_not_contacted_or_stopped(self):
        row=self.service.propose('task','dev',self.port)
        with socket.socket() as unrelated:
            unrelated.bind(('127.0.0.1',self.port));unrelated.listen()
            with patch.object(previews.subprocess,'Popen',side_effect=AssertionError('executed')):
                with self.assertRaises(OSError):self.service.execute('task',self.request(row))
            self.assertGreater(unrelated.fileno(),0)

    @unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS')=='1','requires synthetic local HTTP')
    def test_preview_http_requires_owner_and_exact_fields(self):
        import http.client
        from http.server import ThreadingHTTPServer
        task='00000000-0000-4000-8000-000000000002'
        self.store.write('UPDATE workspaces SET task_id=? WHERE task_id=?',(task,'task'))
        old_auth,old_service=server.AUTH,server._PREVIEWS
        server.STORE,server.AUTH,server._PREVIEWS=self.store,self.host.AUTH,self.service
        http=ThreadingHTTPServer(('127.0.0.1',0),server.App)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def call(body,authorized=True):
            client=http_client.HTTPConnection('127.0.0.1',http.server_port,timeout=5)
            headers={'Content-Type':'application/json'}
            if authorized:headers['Authorization']='Bearer synthetic-preview-owner-000000000000000'
            client.request('POST',f'/api/tasks/{task}/preview/propose',json.dumps(body),headers)
            response=client.getresponse();result=response.status,json.loads(response.read());client.close();return result
        http_client=__import__('http.client',fromlist=['HTTPConnection'])
        try:
            self.assertEqual(call({'script':'dev','port':self.port},False)[0],401)
            self.assertEqual(call({'script':'dev','port':self.port,'command':'arbitrary'})[0],400)
            self.assertEqual(call({'script':'dev','port':self.port})[0],201)
            self.assertFalse(self.service.active)
        finally:
            http.shutdown();http.server_close();thread.join();server.AUTH,server._PREVIEWS=old_auth,old_service

    @unittest.skipUnless(platform.system()=='Darwin' and shutil.which('node'),'requires actual Mac process boundary')
    def test_real_loopback_preview_readiness_logs_stop_and_no_replay(self):
        row=self.service.propose('task','dev',self.port)
        self.service.execute('task',self.request(row))
        ready=self.wait('running')
        self.assertIn('preview listening',ready['logs']);self.assertGreater(ready['process_id'],0)
        with self.assertRaises(ValueError):self.service.execute('task',self.request(row))
        self.assertTrue(self.service.stop('task'));self.wait('stopped')
        self.assertTrue(self.service.close())
        self.service.available(self.port)

    @unittest.skipUnless(platform.system()=='Darwin' and shutil.which('node'),'requires actual Mac process boundary')
    def test_wildcard_request_is_confined_and_project_write_is_denied(self):
        (self.workspace/'server.js').write_text("try {require('fs').writeFileSync('UNEXPECTED','bad')} catch(e){console.log('write denied')} require('http').createServer((q,r)=>r.end('x')).listen(Number(process.env.PORT),'0.0.0.0');")
        row=self.service.propose('task','dev',self.port)
        self.service.execute('task',self.request(row))
        result=self.wait('running')
        self.assertFalse((self.workspace/'UNEXPECTED').exists())
        self.assertIn('write denied',result['logs'])
        self.assertTrue(self.service.owned_listener(result['process_id'],self.port))
        self.service.stop('task');self.wait('stopped');self.service.close()
        self.service.available(self.port)

    @unittest.skipUnless(platform.system()=='Darwin' and shutil.which('node'),'requires actual Mac process boundary')
    def test_new_raw_bind_and_outbound_connect_are_denied(self):
        child = "const n=require('net');const s=n.createServer();s.on('error',e=>console.log('bind',e.code));s.listen("+str(self.port)+",'0.0.0.0',()=>{console.log('UNEXPECTED LISTENER');s.close()});const c=n.createConnection({host:'127.0.0.1',port:1});c.on('error',e=>console.log('connect',e.code));setTimeout(()=>process.exit(),300);"
        entry = "const r=require('child_process').spawnSync(process.execPath,['-e',"+json.dumps(child)+"],{encoding:'utf8'});console.log(r.stdout,r.stderr);require('http').createServer((q,r)=>r.end('ok')).listen(Number(process.env.PORT),process.env.HOST);"
        (self.workspace/'server.js').write_text(entry)
        row=self.service.propose('task','dev',self.port)
        self.service.execute('task',self.request(row));result=self.wait('running')
        self.assertRegex(result['logs'],r'bind (EPERM|EACCES)')
        self.assertRegex(result['logs'],r'connect (EPERM|EACCES)')
        self.assertNotIn('UNEXPECTED LISTENER',result['logs'])

    @unittest.skipUnless(platform.system()=='Darwin' and shutil.which('node'),'requires actual Mac process boundary')
    def test_backend_hard_crash_stops_its_owned_listener(self):
        receipt=self.root/'child-receipt.json'
        script = """import json,sys,time
from pathlib import Path
from tests.test_previews import PreviewTests
case=PreviewTests('test_review_does_not_start_any_process');case.setUp()
row=case.service.propose('task','dev',case.port)
case.service.execute('task',case.request(row));result=case.wait('running')
Path(sys.argv[1]).write_text(json.dumps({'port':case.port,'pid':result['process_id']}))
while True:time.sleep(.2)
"""
        with (self.root/'backend.log').open('wb') as output:
            backend=subprocess.Popen([sys.executable,'-c',script,str(receipt)],stdout=output,stderr=subprocess.STDOUT,
                                     env={**os.environ,'TMPDIR':str(self.root)})
            try:
                deadline=time.monotonic()+15
                while not receipt.exists() and time.monotonic()<deadline:
                    if backend.poll() is not None:self.fail((self.root/'backend.log').read_text())
                    time.sleep(.1)
                self.assertTrue(receipt.exists())
                port=json.loads(receipt.read_text())['port']
                backend.kill();backend.wait(timeout=5)
                deadline=time.monotonic()+6
                while time.monotonic()<deadline:
                    with socket.socket() as probe:
                        if probe.connect_ex(('127.0.0.1',port))!=0:break
                    time.sleep(.1)
                else:self.fail('Owned listener survived backend hard crash')
            finally:
                if backend.poll() is None:backend.kill();backend.wait()


if __name__=='__main__':unittest.main()
