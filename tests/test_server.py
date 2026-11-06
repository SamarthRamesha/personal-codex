import json, os, subprocess, sys, tempfile, threading, unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).parents[1]))
import app.server as server
from app import conversations
from app.server import execute_in_workspace, invoke_provider, merge_preview, parse_command, plan_for, provider_approval_kind, provider_invocation_detail, redacted, repository_summary, safe_project_path, unavailable_provider_transport, validate_provider_config, validate_provider_prompt, visible_files

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
  def test_merge_preview_reports_conflicts_without_modifying_repository(self):
    with tempfile.TemporaryDirectory() as d:
      repo=Path(d)
      def git(*args): return subprocess.run(["git",*args],cwd=repo,check=True,capture_output=True,text=True)
      git("init"); git("config","user.email","test@example.invalid"); git("config","user.name","Test")
      (repo/'README.md').write_text('base\n'); git("add","README.md"); git("commit","-m","base")
      target=git("symbolic-ref","--short","HEAD").stdout.strip()
      git("checkout","-b","task-branch"); (repo/'README.md').write_text('task\n'); git("commit","-am","task change")
      git("checkout",target); (repo/'README.md').write_text('target\n'); git("commit","-am","target change")
      preview=merge_preview(str(repo),"task-branch")
      self.assertFalse(preview['can_merge']); self.assertEqual(preview['target'],target)
      self.assertIn('conflict',preview['detail'].lower()); self.assertEqual((repo/'README.md').read_text(),'target\n')
  def test_provider_metadata_requires_explicit_cloud_consent(self):
    local=validate_provider_config('ollama','http://127.0.0.1:11434','qwen','',False)
    self.assertEqual(local['cloud_allowed'],0)
    with self.assertRaises(ValueError): validate_provider_config('openai-compatible','https://provider.example/v1','model','API_KEY',False)
  def test_provider_secret_reference_is_only_an_environment_variable_name(self):
    with self.assertRaises(ValueError): validate_provider_config('openai-compatible','https://provider.example/v1','model','sk-secret-value',True)
  def test_injected_provider_transport_has_no_secret_or_network_dependency(self):
    provider={'id':'provider-1','kind':'ollama','endpoint':'http://127.0.0.1:11434','model':'fixture','cloud_allowed':0}
    seen=[]
    result=invoke_provider(provider,'hello',lambda request: seen.append(request) or {'text':'deterministic reply'})
    self.assertEqual(result['text'],'deterministic reply'); self.assertNotIn('secret_ref',seen[0])
    self.assertNotEqual(provider_invocation_detail('task-1',provider,'hello'),provider_invocation_detail('task-1',provider,'changed'))
  def test_fail_closed_transport_and_prompt_guards(self):
    provider={'id':'provider-1','kind':'ollama','endpoint':'http://127.0.0.1:11434','model':'fixture','cloud_allowed':0}
    self.assertIsNone(server.PROVIDER_TRANSPORT)
    with self.assertRaises(ValueError): invoke_provider(provider,'hello',unavailable_provider_transport)
    with self.assertRaises(ValueError): invoke_provider(provider,'   ',lambda request: {'text':'unreachable'})
    with self.assertRaises(ValueError): validate_provider_prompt('x'*20_001)
  def test_provider_approval_binds_endpoint_and_cloud_transmission_kind(self):
    local={'id':'p1','kind':'ollama','endpoint':'http://127.0.0.1:11434','model':'m','cloud_allowed':0}
    cloud={'id':'p2','kind':'openai-compatible','endpoint':'https://provider.example/v1','model':'m','cloud_allowed':1}
    self.assertEqual(provider_approval_kind(local),'provider-invoke'); self.assertEqual(provider_approval_kind(cloud),'network')
    local_detail=json.loads(provider_invocation_detail('task-1',local,'hello'))
    moved_detail=json.loads(provider_invocation_detail('task-1',{**local,'endpoint':'http://127.0.0.1:11435'},'hello'))
    self.assertNotEqual(local_detail['refs'],moved_detail['refs']); self.assertIs(local_detail['refs']['cloud_allowed'],False)

@unittest.skipUnless(os.getenv("PERSONAL_CODEX_HTTP_TESTS") == "1", "requires an explicitly enabled loopback listener")
class HttpLifecycleTests(unittest.TestCase):
  """End-to-end security lifecycle; enabled only in an approved listener environment."""
  def setUp(self):
    self.tmp=tempfile.TemporaryDirectory(); base=Path(self.tmp.name)
    self.old_data, self.old_db, self.old_store=server.DATA, server.DB_PATH, server.STORE
    self.old_transport=server.PROVIDER_TRANSPORT
    server.DATA=base/'control-data'; server.DB_PATH=server.DATA/'test.db'; server.STORE=server.Store()
    self.repo=base/'repo'; self.repo.mkdir()
    for args in (["git","init"],["git","config","user.email","test@example.invalid"],["git","config","user.name","Test"],): subprocess.run(args,cwd=self.repo,check=True,capture_output=True)
    (self.repo/'README.md').write_text('# fixture\n'); subprocess.run(["git","add","README.md"],cwd=self.repo,check=True,capture_output=True); subprocess.run(["git","commit","-m","fixture"],cwd=self.repo,check=True,capture_output=True)
    self.http=ThreadingHTTPServer(('127.0.0.1',0),server.App); self.thread=threading.Thread(target=self.http.serve_forever,daemon=True); self.thread.start(); self.base=f'http://127.0.0.1:{self.http.server_port}'
  def tearDown(self):
    self.http.shutdown(); self.http.server_close(); self.thread.join(); server.STORE.conn.close(); server.DATA, server.DB_PATH, server.STORE, server.PROVIDER_TRANSPORT=self.old_data,self.old_db,self.old_store,self.old_transport; self.tmp.cleanup()
  def request(self,path,method='GET',data=None):
    body=json.dumps(data).encode() if data is not None else None; request=Request(self.base+path,data=body,method=method,headers={'Content-Type':'application/json'})
    try:
      with urlopen(request,timeout=3) as response: return response.status,json.loads(response.read())
    except HTTPError as error: return error.code,json.loads(error.read())
  def test_approval_workspace_execution_lifecycle(self):
    status,health=self.request('/api/health'); self.assertEqual((status,health['ok']),(200,True))
    status,project=self.request('/api/projects','POST',{'name':'fixture','path':str(self.repo)}); self.assertEqual(status,201)
    status,provider=self.request('/api/providers','POST',{'kind':'ollama','endpoint':'http://127.0.0.1:11434','model':'fixture','secret_ref':''}); self.assertEqual(status,201)
    status,capabilities=self.request(f"/api/providers/{provider['id']}/capabilities"); self.assertEqual((status,capabilities['invocation_requires_approval']),(200,True))
    status,cloud_denied=self.request('/api/providers','POST',{'kind':'openai-compatible','endpoint':'https://provider.example/v1','model':'fixture','secret_ref':'API_KEY'}); self.assertEqual(status,400)
    status,task=self.request('/api/tasks','POST',{'project_id':project['id'],'prompt':'run a safe check'}); self.assertEqual(status,201); task_id=task['id']
    prompt='review the fixture without leaving this machine'
    status,denied=self.request(f'/api/tasks/{task_id}/invoke','POST',{'provider_id':provider['id'],'prompt':prompt}); self.assertEqual(status,403)
    status,approval=self.request(f'/api/tasks/{task_id}/provider-request','POST',{'provider_id':provider['id'],'prompt':prompt}); self.assertEqual(status,201); self.assertEqual(approval['kind'],'provider-invoke'); self.assertFalse(approval['cloud_allowed'])
    server.PROVIDER_TRANSPORT=lambda request: {'text':'deterministic reply from '+request['model']}
    self.assertEqual(self.request(f"/api/approvals/{approval['id']}",'PATCH',{'status':'approved'})[0],200)
    status,invoked=self.request(f'/api/tasks/{task_id}/invoke','POST',{'provider_id':provider['id'],'prompt':prompt}); self.assertEqual(status,200); self.assertTrue(invoked['text'].startswith('deterministic reply')); self.assertEqual(len(invoked['prompt_sha256']),64); self.assertFalse(invoked['cloud_allowed'])
    status,changed_prompt=self.request(f'/api/tasks/{task_id}/invoke','POST',{'provider_id':provider['id'],'prompt':prompt+' changed'}); self.assertEqual(status,403)
    status,invocations=self.request(f'/api/tasks/{task_id}/invocations'); self.assertEqual((status,len(invocations)),(200,1)); self.assertNotIn(prompt,invocations[0]['response']); self.assertIn('deterministic reply',invocations[0]['response'])
    status,cloud_provider=self.request('/api/providers','POST',{'kind':'openai-compatible','endpoint':'https://provider.example/v1','model':'fixture-cloud','secret_ref':'PROVIDER_API_KEY','cloud_allowed':True}); self.assertEqual(status,201)
    status,cloud_request=self.request(f'/api/tasks/{task_id}/provider-request','POST',{'provider_id':cloud_provider['id'],'prompt':prompt}); self.assertEqual((status,cloud_request['kind'],cloud_request['cloud_allowed']),(201,'network',True))
    status,cloud_denied=self.request(f'/api/tasks/{task_id}/invoke','POST',{'provider_id':cloud_provider['id'],'prompt':prompt}); self.assertEqual(status,403); self.assertIn('network',cloud_denied['error'])
    self.assertEqual(self.request(f"/api/approvals/{cloud_request['id']}",'PATCH',{'status':'approved'})[0],200)
    status,cloud_invoked=self.request(f'/api/tasks/{task_id}/invoke','POST',{'provider_id':cloud_provider['id'],'prompt':prompt}); self.assertEqual(status,200); self.assertTrue(cloud_invoked['cloud_allowed']); self.assertEqual(cloud_invoked['prompt_sha256'],invoked['prompt_sha256'])
    status,invocations=self.request(f'/api/tasks/{task_id}/invocations'); self.assertEqual((status,len(invocations)),(200,2))
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
    workspace_path=Path(workspace['path']); (workspace_path/'feature.txt').write_text('merged fixture\n')
    subprocess.run(["git","add","feature.txt"],cwd=workspace_path,check=True,capture_output=True); subprocess.run(["git","commit","-m","feature fixture"],cwd=workspace_path,check=True,capture_output=True)
    status,recovery=self.request(f'/api/tasks/{task_id}/workspace-recovery'); self.assertEqual((status,recovery['clean']),(200,True))
    status,approval=self.request(f'/api/tasks/{task_id}/workspace-release-request','POST',{}); self.assertEqual(status,201)
    self.assertEqual(self.request(f"/api/approvals/{approval['id']}",'PATCH',{'status':'approved'})[0],200)
    status,released=self.request(f'/api/tasks/{task_id}/workspace-release','POST',{}); self.assertEqual((status,released['branch_preserved']),(200,True))
    status,recovery=self.request(f'/api/tasks/{task_id}/workspace-recovery'); self.assertEqual((status,recovery['present'],recovery['clean']),(200,False,None))
    status,preview=self.request(f'/api/tasks/{task_id}/merge-preview'); self.assertEqual((status,preview['can_merge']),(200,True))
    status,denied=self.request(f'/api/tasks/{task_id}/merge','POST',{}); self.assertEqual(status,403)
    status,approval=self.request(f'/api/tasks/{task_id}/merge-request','POST',{}); self.assertEqual(status,201)
    self.assertEqual(self.request(f"/api/approvals/{approval['id']}",'PATCH',{'status':'approved'})[0],200)
    (self.repo/'target.txt').write_text('target advanced\n'); subprocess.run(["git","add","target.txt"],cwd=self.repo,check=True,capture_output=True); subprocess.run(["git","commit","-m","target advanced"],cwd=self.repo,check=True,capture_output=True)
    status,stale=self.request(f'/api/tasks/{task_id}/merge','POST',{}); self.assertEqual(status,403); self.assertIn('current target',stale['error'])
    status,approval=self.request(f'/api/tasks/{task_id}/merge-request','POST',{}); self.assertEqual(status,201)
    self.assertEqual(self.request(f"/api/approvals/{approval['id']}",'PATCH',{'status':'approved'})[0],200)
    status,merged=self.request(f'/api/tasks/{task_id}/merge','POST',{}); self.assertEqual((status,merged['branch_preserved']),(200,True)); self.assertTrue((self.repo/'feature.txt').is_file())
    status,denied=self.request(f'/api/tasks/{task_id}/branch-delete','POST',{}); self.assertEqual(status,403)
    status,approval=self.request(f'/api/tasks/{task_id}/branch-delete-request','POST',{}); self.assertEqual(status,201)
    self.assertEqual(self.request(f"/api/approvals/{approval['id']}",'PATCH',{'status':'approved'})[0],200)
    status,deleted=self.request(f'/api/tasks/{task_id}/branch-delete','POST',{}); self.assertEqual((status,deleted['branch_deleted']),(200,True))

class ExecutionClaimTests(unittest.TestCase):
    """The execution claim shares one sqlite connection with streamed chat writes."""

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); base=Path(self.tmp.name)
        self.old_data,self.old_db,self.old_store=server.DATA,server.DB_PATH,server.STORE
        server.DATA=base/'claim-data'; server.DB_PATH=server.DATA/'test.db'; server.STORE=server.Store()
        self.store=server.STORE
        at=server.now()
        self.store.write("INSERT INTO projects VALUES (?,?,?,?)",('p1','Fixture',self.tmp.name,at))
        self.store.write("INSERT INTO proposals (id,task_id,workspace_branch,workspace_path,summary,operations,digest,status,created_at) "
                         "VALUES (?,?,?,?,?,?,?,?,?)",('prop-1','task-1','b',self.tmp.name,'s','[]','d','pending',at))
        self.store.write("INSERT INTO rounds (id,task_id,round_number,provider_id,model,prompt_sha256,proposal_id,status,created_at,updated_at) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?)",('round-1','task-1',1,'prov-1','m','sha','prop-1','awaiting-approval',at,at))

    def tearDown(self):
        server.STORE.conn.close()
        server.DATA,server.DB_PATH,server.STORE=self.old_data,self.old_db,self.old_store
        self.tmp.cleanup()

    def test_a_claim_takes_the_proposal_and_round_exactly_once(self):
        self.assertEqual(self.store.claim_execution('prop-1','round-1'),'ok')
        self.assertEqual(self.store.one("SELECT status FROM proposals WHERE id='prop-1'")['status'],'executing')
        self.assertEqual(self.store.one("SELECT status FROM rounds WHERE id='round-1'")['status'],'executing')
        # A second claim loses instead of re-running the same approved proposal.
        self.assertEqual(self.store.claim_execution('prop-1','round-1'),'proposal')

    def test_a_lost_claim_leaves_the_connection_usable(self):
        self.store.write("UPDATE proposals SET status='executing' WHERE id='prop-1'")
        self.assertEqual(self.store.claim_execution('prop-1','round-1'),'proposal')
        # The rollback of a lost claim must not strand an open transaction for the next writer.
        self.store.write("INSERT INTO projects VALUES (?,?,?,?)",('p2','After',str(Path(self.tmp.name)/'after'),server.now()))
        self.assertIsNotNone(self.store.one("SELECT id FROM projects WHERE id='p2'"))
        self.assertEqual(self.store.one("SELECT status FROM rounds WHERE id='round-1'")['status'],'awaiting-approval')

    def test_streamed_chat_writes_survive_a_concurrent_claim(self):
        conversation=conversations.create_conversation(self.store)
        message=conversations.new_message(self.store,conversation['id'],'assistant','',status='streaming')
        expected=40; errors=[]
        def writer():
            try:
                for index in range(expected):
                    conversations.append_chunk(self.store,conversation['id'],message['id'],f'chunk{index}')
            except Exception as error:
                errors.append(error)
        thread=threading.Thread(target=writer); thread.start()
        for _ in range(40):
            self.store.claim_execution('prop-1','round-1')
        thread.join()
        self.assertEqual(errors,[])
        chunks=self.store.rows("SELECT text FROM message_chunks WHERE message_id=? ORDER BY seq",(message['id'],))
        self.assertEqual(len(chunks),expected)

if __name__ == '__main__': unittest.main()
