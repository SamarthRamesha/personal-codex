"""Authentication, browser request attacks and fail-closed listener policy."""
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from app import security, server


class AuthPolicyTests(unittest.TestCase):
    def test_remote_listener_requires_tailnet_auth_and_tls(self):
        for host in ('0.0.0.0', '192.168.1.12', '8.8.8.8', '::', 'example.com'):
            with self.assertRaises(ValueError): security.private_bind(host, True, True)
        for auth, tls in ((False,False),(False,True),(True,False)):
            with self.assertRaises(ValueError): security.private_bind('100.100.100.100', auth, tls)
        security.private_bind('100.100.100.100', True, True)
        security.private_bind('fd7a:115c:a1e0::123', True, True)
        security.private_bind('127.0.0.1', False, False)

    def test_sessions_expire_logout_and_do_not_store_secret_values(self):
        clock=[0.0]; token='test-owner-token-'+'x'*32
        auth=security.OwnerAuth(token,ttl=60,clock=lambda:clock[0])
        session=auth.login(token,'local')
        headers={'Cookie':f'{security.COOKIE}={session}'}
        self.assertTrue(auth.authorized(headers))
        self.assertNotIn(session,auth.sessions)
        self.assertNotIn(token,repr(auth.__dict__))
        clock[0]=61
        self.assertFalse(auth.authorized(headers))
        session=auth.login(token,'local');headers={'Cookie':f'{security.COOKIE}={session}'}
        auth.logout(headers);self.assertFalse(auth.authorized(headers))
        self.assertTrue(auth.authorized({'Authorization':'Bearer '+token}))
        self.assertFalse(auth.authorized({'Authorization':'Bearer wrong'}))

    def test_approval_decision_is_atomic_under_competing_requests(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(server, 'DATA', Path(directory)), patch.object(server, 'DB_PATH', Path(directory)/'test.db'):
                store=server.Store()
            try:
                store.write('INSERT INTO approvals VALUES (?,?,?,?,?,?)',('a','p','modify','exact','pending',1))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results=list(pool.map(lambda status:store.decide_approval('a',status),('approved','rejected')))
                self.assertEqual(sum(results),1)
                decided=store.one('SELECT status FROM approvals WHERE id=?',('a',))['status']
                self.assertFalse(store.decide_approval('a','rejected' if decided=='approved' else 'approved'))
                self.assertEqual(store.one('SELECT status FROM approvals WHERE id=?',('a',))['status'],decided)
            finally:store.conn.close()

    def test_login_attempts_are_rate_limited_and_bounded(self):
        auth=security.OwnerAuth('x'*48)
        for _ in range(5):
            with self.assertRaises(PermissionError):auth.login('wrong','peer')
        with self.assertRaisesRegex(PermissionError,'Too many'):auth.login('x'*48,'peer')
        for n in range(300):
            with self.assertRaises(PermissionError):auth.login('wrong',str(n))
        self.assertLessEqual(len(auth.failures),256)

    def test_token_file_rejects_world_readable_symlink_and_empty_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'token';path.write_text('x'*48);path.chmod(0o644)
            with patch.dict(os.environ,{'PERSONAL_CODEX_TOKEN_FILE':str(path)}):
                with self.assertRaises(ValueError):security.OwnerAuth.from_env()
                path.chmod(0o600);self.assertTrue(security.OwnerAuth.from_env().enabled)
            link=Path(directory)/'link';link.symlink_to(path)
            with patch.dict(os.environ,{'PERSONAL_CODEX_TOKEN_FILE':str(link)}):
                with self.assertRaises(ValueError):security.OwnerAuth.from_env()
            path.write_text('')
            with patch.dict(os.environ,{'PERSONAL_CODEX_TOKEN_FILE':str(path)}):
                with self.assertRaises(ValueError):security.OwnerAuth.from_env()


@unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS')=='1','requires explicitly enabled loopback listener')
class AuthHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();base=Path(self.tmp.name)
        self.old=(server.DATA,server.DB_PATH,server.STORE,server.AUTH)
        server.DATA=base/'data';server.DB_PATH=server.DATA/'test.db';server.STORE=server.Store()
        self.token='synthetic-owner-token-'+'x'*32;server.AUTH=security.OwnerAuth(self.token)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.App)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join()
        server.STORE.conn.close();server.DATA,server.DB_PATH,server.STORE,server.AUTH=self.old
        self.tmp.cleanup()
    def request(self,method,path,body=None,headers=None):
        client=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
        data=json.dumps(body).encode() if body is not None else None
        client.request(method,path,data,{'Content-Type':'application/json',**(headers or {})})
        response=client.getresponse();result=(response.status,dict(response.getheaders()),response.read())
        client.close();return result
    def test_all_sensitive_methods_and_streams_require_owner_auth(self):
        for method,path,body in [('GET','/api/projects',None),('GET','/api/connection',None),('GET','/api/conversations/x/messages/y/stream',None),('POST','/api/projects',{}),('PATCH','/api/approvals/x',{}),('DELETE','/api/conversations/x',None),('HEAD','/api/projects',None)]:
            status,_,_=self.request(method,path,body)
            self.assertEqual(status,401,(method,path))
        self.assertEqual(self.request('GET','/api/health')[0],200)
        status,_,body=self.request('GET','/api/connection',headers={'Authorization':'Bearer '+self.token})
        self.assertEqual(status,200);self.assertTrue(json.loads(body)['authenticated'])
    def test_cookie_login_logout_and_bad_token(self):
        self.assertEqual(self.request('POST','/api/session',{'token':'wrong'})[0],401)
        status,headers,_=self.request('POST','/api/session',{'token':self.token})
        self.assertEqual(status,200);cookie=headers['Set-Cookie']
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
        cookie=cookie.split(';')[0]
        self.assertEqual(self.request('GET','/api/projects',headers={'Cookie':cookie})[0],200)
        self.assertEqual(self.request('DELETE','/api/session',headers={'Cookie':cookie})[0],200)
        self.assertEqual(self.request('GET','/api/projects',headers={'Cookie':cookie})[0],401)
    def test_cross_origin_and_dns_rebinding_are_rejected_even_with_token(self):
        for attack in ({'Origin':'https://evil.example'},{'Origin':'null'},{'Host':'evil.example'},{'Sec-Fetch-Site':'cross-site'}):
            headers={'Authorization':'Bearer '+self.token,**attack}
            self.assertEqual(self.request('POST','/api/conversations',{},headers)[0],403)
        self.assertEqual(server.STORE.rows('SELECT * FROM conversations'),[])
    def test_oversized_and_malformed_bodies_fail_before_dispatch(self):
        auth={'Authorization':'Bearer '+self.token}
        self.assertEqual(self.request('POST','/api/conversations',headers={**auth,'Content-Length':'1000001'})[0],413)
        self.assertEqual(self.request('POST','/api/conversations',[],auth)[0],400)
        self.assertEqual(self.request('PATCH','/api/approvals/x',[],auth)[0],400)
        self.assertEqual(self.request('POST','/api/conversations',{}, {**auth,'Content-Type':'text/plain'})[0],415)
    def test_cancel_during_provider_planning_never_publishes_an_executable_proposal(self):
        import subprocess
        repo=Path(self.tmp.name)/'planning-repo';repo.mkdir();(repo/'safe.py').write_text('print(1)')
        for args in (['git','init'],['git','config','user.email','fixture@example.invalid'],['git','config','user.name','Fixture'],['git','add','.'],['git','commit','-m','fixture']):
            subprocess.run(args,cwd=repo,check=True,capture_output=True)
        auth={'Authorization':'Bearer '+self.token}
        def call(path,body,method='POST'):
            status,_,response=self.request(method,path,body,auth)
            return status,json.loads(response)
        _,project=call('/api/projects',{'path':str(repo)})
        _,provider=call('/api/providers',{'kind':'ollama','endpoint':'http://127.0.0.1:11434','model':'fixture'})
        _,task=call('/api/tasks',{'project_id':project['id'],'prompt':'inspect the fixture'})
        tid=task['id'];_,approval=call(f'/api/tasks/{tid}/workspace-request',{})
        call('/api/approvals/'+approval['id'],{'status':'approved'},'PATCH');call(f'/api/tasks/{tid}/workspace',{})
        _,approval=call(f'/api/tasks/{tid}/agent/round/request',{'provider_id':provider['id']})
        call('/api/approvals/'+approval['approval_id'],{'status':'approved'},'PATCH')
        started=threading.Event();release=threading.Event();result=[]
        def transport(request):
            started.set();release.wait(2)
            return {'text':'{"summary":"inspect","status":"continue","operations":[{"tool":"list_files","path":"."}]}'}
        with patch.object(server,'PROVIDER_TRANSPORT',transport):
            worker=threading.Thread(target=lambda:result.append(call(f'/api/tasks/{tid}/agent/round/plan',{'provider_id':provider['id']})))
            worker.start()
            try:
                self.assertTrue(started.wait(2));call(f'/api/tasks/{tid}/cancel',{})
            finally:release.set();worker.join(3)
        self.assertEqual(result[0][0],409)
        self.assertEqual(server.STORE.rows('SELECT * FROM proposals WHERE task_id=?',(tid,)),[])
        self.assertEqual(server.STORE.one('SELECT status FROM tasks WHERE id=?',(tid,))['status'],'cancelled')

    def test_project_reader_ignores_secrets_traversal_symlinks_and_gitignore(self):
        repo=Path(self.tmp.name)/'repo';repo.mkdir()
        (repo/'safe.py').write_text('print("safe")')
        (repo/'.env').write_text('SECRET=example')
        (repo/'.gitignore').write_text('private.txt\n')
        (repo/'private.txt').write_text('private')
        (repo/'link.py').symlink_to(repo/'safe.py')
        auth={'Authorization':'Bearer '+self.token}
        _,_,body=self.request('POST','/api/projects',{'path':str(repo)},auth);pid=json.loads(body)['id']
        status,_,body=self.request('GET',f'/api/projects/{pid}/files',headers=auth)
        self.assertEqual(status,200);files=json.loads(body)['files'];self.assertIn('safe.py',files)
        for path in ('.env','private.txt','link.py','../outside.py'):
            self.assertNotIn(path,files)
            self.assertEqual(self.request('GET',f'/api/projects/{pid}/file?path={path}',headers=auth)[0],403)
