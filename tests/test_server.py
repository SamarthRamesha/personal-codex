import json, os, subprocess, sys, tempfile, threading, unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).parents[1]))
import app.server as server
from app.server import execute_in_workspace, parse_command, plan_for, redacted, repository_summary, safe_project_path, visible_files

class SecurityAndPlanningTests(unittest.TestCase):
  def test_secret_named_files_not_visible(self):
    with tempfile.TemporaryDirectory() as d:
      Path(d,'.env').write_text('SECRET=x'); Path(d,'main.py').write_text('print(1)')
      self.assertEqual(visible_files(Path(d)), ['main.py'])
  def test_existing_directory_is_accepted(self):
    with tempfile.TemporaryDirectory() as d: self.assertEqual(safe_project_path(d), Path(d).resolve())
  def test_plan_has_independent_review(self):
    plan=plan_for('add a test', {'manifests':['pyproject.toml'], 'files':[]})
    self.assertEqual([x['agent'] for x in plan], ['planner','developer','testing','reviewer'])
  def test_summary_detects_git(self):
    with tempfile.TemporaryDirectory() as d:
      Path(d,'.git').mkdir(); self.assertTrue(repository_summary(Path(d))['git'])
  def test_shell_syntax_is_refused(self):
    with self.assertRaises(ValueError): parse_command('pytest && curl example.com')
  def test_output_secrets_are_redacted(self):
    self.assertIn('[REDACTED]', redacted('API_KEY=abc123 failure'))
  def test_timeout_range_is_enforced_before_execution(self):
    with self.assertRaises(ValueError): execute_in_workspace('/tmp', 'python3 -c "print(1)"', 301)

@unittest.skipUnless(os.getenv("PERSONAL_CODEX_HTTP_TESTS") == "1", "requires an explicitly enabled loopback listener")
class HttpLifecycleTests(unittest.TestCase):
  """End-to-end security lifecycle; enabled only in an approved listener environment."""
  def setUp(self):
    self.tmp=tempfile.TemporaryDirectory(); base=Path(self.tmp.name)
    self.old_data, self.old_db, self.old_store=server.DATA, server.DB_PATH, server.STORE
    server.DATA=base/'control-data'; server.DB_PATH=server.DATA/'test.db'; server.STORE=server.Store()
    self.repo=base/'repo'; self.repo.mkdir()
    for args in (["git","init"],["git","config","user.email","test@example.invalid"],["git","config","user.name","Test"],): subprocess.run(args,cwd=self.repo,check=True,capture_output=True)
    (self.repo/'README.md').write_text('# fixture\n'); subprocess.run(["git","add","README.md"],cwd=self.repo,check=True,capture_output=True); subprocess.run(["git","commit","-m","fixture"],cwd=self.repo,check=True,capture_output=True)
    self.http=ThreadingHTTPServer(('127.0.0.1',0),server.App); self.thread=threading.Thread(target=self.http.serve_forever,daemon=True); self.thread.start(); self.base=f'http://127.0.0.1:{self.http.server_port}'
  def tearDown(self):
    self.http.shutdown(); self.http.server_close(); self.thread.join(); server.STORE.conn.close(); server.DATA, server.DB_PATH, server.STORE=self.old_data,self.old_db,self.old_store; self.tmp.cleanup()
  def request(self,path,method='GET',data=None):
    body=json.dumps(data).encode() if data is not None else None; request=Request(self.base+path,data=body,method=method,headers={'Content-Type':'application/json'})
    try:
      with urlopen(request,timeout=3) as response: return response.status,json.loads(response.read())
    except HTTPError as error: return error.code,json.loads(error.read())
  def test_approval_workspace_execution_lifecycle(self):
    status,health=self.request('/api/health'); self.assertEqual((status,health['ok']),(200,True))
    status,project=self.request('/api/projects','POST',{'name':'fixture','path':str(self.repo)}); self.assertEqual(status,201)
    status,task=self.request('/api/tasks','POST',{'project_id':project['id'],'prompt':'run a safe check'}); self.assertEqual(status,201); task_id=task['id']
    status,denied=self.request(f'/api/tasks/{task_id}/workspace','POST',{}); self.assertEqual(status,403); self.assertIn('approved',denied['error'])
    status,approval=self.request(f'/api/tasks/{task_id}/workspace-request','POST',{}); self.assertEqual(status,201)
    self.assertEqual(self.request(f"/api/approvals/{approval['id']}",'PATCH',{'status':'approved'})[0],200)
    self.assertEqual(self.request(f"/api/approvals/{approval['id']}",'PATCH',{'status':'rejected'})[0],409)
    status,workspace=self.request(f'/api/tasks/{task_id}/workspace','POST',{}); self.assertEqual(status,201); self.assertTrue(Path(workspace['path']).is_dir())
    command='python3 -c "print(42)"'
    status,denied=self.request(f'/api/tasks/{task_id}/execute','POST',{'command':command}); self.assertEqual(status,403)
    status,approval=self.request(f'/api/tasks/{task_id}/execution-request','POST',{'command':command}); self.assertEqual(status,201)
    self.assertEqual(self.request(f"/api/approvals/{approval['id']}",'PATCH',{'status':'approved'})[0],200)
    status,execution=self.request(f'/api/tasks/{task_id}/execute','POST',{'command':command}); self.assertEqual(status,200); self.assertEqual(execution['exit_code'],0); self.assertIn('42',execution['output'])
    status,events=self.request(f'/api/tasks/{task_id}/events'); self.assertEqual(status,200); self.assertGreaterEqual(len(events),4)
    status,recovery=self.request(f'/api/tasks/{task_id}/workspace-recovery'); self.assertEqual((status,recovery['clean']),(200,True))
    status,approval=self.request(f'/api/tasks/{task_id}/workspace-release-request','POST',{}); self.assertEqual(status,201)
    self.assertEqual(self.request(f"/api/approvals/{approval['id']}",'PATCH',{'status':'approved'})[0],200)
    status,released=self.request(f'/api/tasks/{task_id}/workspace-release','POST',{}); self.assertEqual((status,released['branch_preserved']),(200,True))
    status,recovery=self.request(f'/api/tasks/{task_id}/workspace-recovery'); self.assertEqual((status,recovery['present'],recovery['clean']),(200,False,None))

if __name__ == '__main__': unittest.main()
