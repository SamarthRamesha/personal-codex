import http.client
import json
import os
from pathlib import Path
import re
import selectors
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from app import runtime,server


class RuntimePolicyTests(unittest.TestCase):
    @unittest.skipUnless(os.getenv("PERSONAL_CODEX_HTTP_TESTS") == "1", "requires explicitly enabled loopback listener")
    def test_loopback_listener_does_not_need_reverse_dns(self):
        with patch("socket.getfqdn", side_effect=AssertionError("Unexpected reverse DNS lookup")):
            with runtime.ControlServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as listener:
                self.assertEqual(listener.server_name, "127.0.0.1")
                self.assertEqual(listener.server_port, listener.server_address[1])

    def test_instance_lock_excludes_other_starts_and_recovers_after_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with runtime.InstanceLock(root):
                with self.assertRaisesRegex(ValueError,'already owns'):
                    with runtime.InstanceLock(root):pass
            with runtime.InstanceLock(root):pass
    def test_symlink_lock_does_not_modify_external_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);outside=root/'untouched';outside.write_text('same')
            data=root/'data';data.mkdir();(data/'.backend.lock').symlink_to(outside)
            with self.assertRaises((ValueError,OSError)):
                with runtime.InstanceLock(data):pass
            self.assertEqual(outside.read_text(),'same')
    def test_disabled_profile_never_starts_interpreter_or_git(self):
        with patch.dict(os.environ,{'PERSONAL_CODEX_EXECUTION_MODE':'disabled'}),patch.object(server.subprocess,'Popen') as spawn,patch.object(server.subprocess,'run') as run:
            for fn in (lambda:server.execute_in_workspace('/synthetic','python3 -c "print(1)"'),
                       lambda:server.git_output('/synthetic',['status']),lambda:server.create_task_workspace('x','/synthetic')):
                with self.assertRaises(ValueError):fn()
            spawn.assert_not_called();run.assert_not_called()
    def test_project_roots_are_enforced_before_file_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);allowed=root/'allowed';outside=root/'outside';allowed.mkdir();outside.mkdir()
            with patch.dict(os.environ,{'PERSONAL_CODEX_PROJECT_ROOTS':str(allowed)}):
                self.assertEqual(server.safe_project_path(str(allowed)),allowed.resolve())
                with self.assertRaises(ValueError):server.safe_project_path(str(outside))
                with self.assertRaises(ValueError):server.safe_project_path('')


@unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS')=='1','requires explicitly enabled loopback listener')
class ServiceProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.token='synthetic-process-owner-'+'x'*32;self.key=self.root/'owner-token';self.key.write_text(self.token);self.key.chmod(0o600)
        self.env={'PATH':os.getenv('PATH',''),'HOME':str(self.root),'LANG':'C',
                  'PERSONAL_CODEX_DATA':str(self.root/'data'),'PERSONAL_CODEX_PORT':'0','PERSONAL_CODEX_TOKEN_FILE':str(self.key),
                  # This disposable process fixture is not a production-capacity test.
                  # Retain real readiness checks without requiring a 200 GB CI runner.
                  'PERSONAL_CODEX_RESERVE_GB':'1','PERSONAL_CODEX_STORAGE_GB':'5'}
        self.process=subprocess.Popen([sys.executable,'app/server.py'],cwd=server.ROOT,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        selector=selectors.DefaultSelector();selector.register(self.process.stdout,selectors.EVENT_READ)
        try:
            self.assertTrue(selector.select(8),'backend did not report startup')
            line=self.process.stdout.readline();match=re.search(r'http://127\.0\.0\.1:(\d+)',line)
            self.assertIsNotNone(match,line);self.port=int(match.group(1))
        finally:selector.close()
    def tearDown(self):
        if self.process.poll() is None:self.process.terminate()
        try:self.process.communicate(timeout=8)
        except subprocess.TimeoutExpired:self.process.kill();self.process.communicate()
        self.tmp.cleanup()
    def call(self,path,body=None):
        client=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3)
        client.request('POST' if body is not None else 'GET',path,json.dumps(body).encode() if body is not None else None,{'Content-Type':'application/json','Authorization':'Bearer '+self.token})
        response=client.getresponse();result=response.status,json.loads(response.read());client.close();return result
    def test_single_instance_readiness_and_persisted_restart(self):
        self.assertEqual(self.call('/api/ready')[0],200)
        _,chat=self.call('/api/conversations',{'title':'persistent fixture'})
        second=subprocess.run([sys.executable,'app/server.py'],cwd=server.ROOT,env=self.env,capture_output=True,text=True,timeout=8)
        self.assertNotEqual(second.returncode,0);self.assertIn('already owns',second.stderr)
        self.assertEqual(self.call('/api/conversations/'+chat['id'])[1]['conversation']['title'],'persistent fixture')
        self.process.send_signal(signal.SIGTERM);self.process.communicate(timeout=8)
        self.assertEqual(self.process.returncode,0)
        connection=sqlite3.connect(self.root/'data'/'personal_codex.db')
        self.assertEqual(connection.execute('SELECT title FROM conversations').fetchone()[0],'persistent fixture');connection.close()
        self.assertEqual((self.root/'data'/'personal_codex.db').stat().st_mode & 0o777,0o600)
    def test_sigterm_cancels_silent_chat_before_database_close(self):
        release=threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length','0')))
                self.send_response(200);self.end_headers();self.wfile.write(b'{"message":{"content":"partial"},"done":false}\n');self.wfile.flush();release.wait(8)
            def log_message(self,*_):pass
        provider=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=provider.serve_forever,daemon=True);thread.start()
        try:
            _,p=self.call('/api/providers',{'kind':'ollama','endpoint':f'http://127.0.0.1:{provider.server_port}','model':'fixture'})
            _,chat=self.call('/api/conversations',{'provider_id':p['id'],'model':'fixture'})
            self.call('/api/conversations/'+chat['id']+'/messages',{'content':'synthetic'})
            for _ in range(30):
                report=self.call('/api/conversations/'+chat['id'])[1]
                if report['conversation']['messages'][-1]['content']=='partial':break
                time.sleep(.05)
            self.assertEqual(report['conversation']['messages'][-1]['content'],'partial')
            self.process.send_signal(signal.SIGTERM);self.process.communicate(timeout=8);self.assertEqual(self.process.returncode,0)
            connection=sqlite3.connect(self.root/'data'/'personal_codex.db')
            row=connection.execute("SELECT status,content FROM messages WHERE role='assistant'").fetchone();connection.close()
            self.assertEqual(row,('stopped','partial'))
        finally:release.set();provider.shutdown();provider.server_close();thread.join()
