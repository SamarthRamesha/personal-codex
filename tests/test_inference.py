import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from app import inference, server, security, conversations, mac_worker
import test_security as fixture


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.old=server.DATA,server.DB_PATH
        server.DATA=self.base/'data';server.DB_PATH=server.DATA/'test.db';self.store=server.Store()
        self.store.write('INSERT INTO providers (id,kind,endpoint,model,secret_ref,cloud_allowed,enabled,created_at) VALUES (?,?,?,?,?,?,?,?)',('p',inference.KIND,'','fixture','',0,1,1))
        self.broker=inference.Broker(self.store);self.broker.poll(['fixture'])
    def tearDown(self):
        self.store.conn.close();server.DATA,server.DB_PATH=self.old;self.tmp.cleanup()
    def submit(self):return self.broker.submit('p','fixture','synthetic prompt')
    def test_chunks_are_ordered_idempotent_and_lease_bound(self):
        jid=self.submit();job=self.broker.poll(['fixture'])
        with self.assertRaises(PermissionError):self.broker.append(jid,'wrong',1,'bad')
        with self.assertRaises(ValueError):self.broker.append(jid,job['lease'],2,'out of order')
        first=self.broker.append(jid,job['lease'],1,'Hello')
        self.assertFalse(first['duplicate'])
        self.assertTrue(self.broker.append(jid,job['lease'],1,'Hello')['duplicate'])
        with self.assertRaises(ValueError):self.broker.append(jid,job['lease'],1,'different')
        self.assertEqual(self.broker.append(jid,job['lease'],2,' world',True)['status'],'complete')
        self.assertEqual(self.store.one('SELECT prompt,content FROM inference_jobs WHERE id=?',(jid,)),{'prompt':'','content':'Hello world'})
    def test_one_worker_claim_and_bounded_queue(self):
        ids=[self.submit() for _ in range(inference.MAX_JOBS)]
        with self.assertRaises(inference.ProviderTransportError):self.submit()
        job=self.broker.poll(['fixture']);self.assertIn(job['id'],ids)
        self.assertIsNone(self.broker.poll(['fixture']))
        self.broker.cancel(job['id'])
        self.assertIsNotNone(self.broker.poll(['fixture']))
    def test_expired_lease_is_never_reclaimed_or_replayed(self):
        jid=self.submit();job=self.broker.poll(['fixture'])
        with patch.object(inference,'now',return_value=inference.now()+inference.LEASE_SECONDS+1):
            self.assertIsNone(self.broker.poll(['fixture']))
            with self.assertRaises(PermissionError):self.broker.heartbeat(jid,job['lease'])
        self.assertEqual(self.store.one('SELECT status FROM inference_jobs WHERE id=?',(jid,))['status'],'expired')
    def test_restart_interrupts_jobs_and_forgets_presence(self):
        jid=self.submit();self.broker.poll(['fixture']);self.store.conn.close();self.store=server.Store();self.broker=inference.Broker(self.store)
        self.assertEqual(self.store.one('SELECT status,prompt FROM inference_jobs WHERE id=?',(jid,)),{'status':'interrupted','prompt':''})
        self.assertFalse(self.broker.catalog()['online'])
        self.assertIsNone(self.broker.poll(['fixture']))
    def test_no_offline_unknown_model_or_arbitrary_provider_submission(self):
        for pid,model in [('p','absent'),('absent','fixture')]:
            with self.assertRaises(inference.ProviderTransportError):self.broker.submit(pid,model,'prompt')
        self.store.write('UPDATE inference_workers SET last_seen=0')
        with self.assertRaisesRegex(inference.ProviderTransportError,'offline'):self.submit()
    def test_utf8_byte_budget_and_error_redaction(self):
        jid=self.submit();job=self.broker.poll(['fixture'])
        with patch.object(inference,'MAX_RESPONSE',5):
            with self.assertRaises(ValueError):self.broker.append(jid,job['lease'],1,'世界')
        self.broker.append(jid,job['lease'],1,error='api_key=synthetic-value')
        self.assertNotIn('synthetic-value',self.store.one('SELECT error FROM inference_jobs WHERE id=?',(jid,))['error'])
    def test_transport_streams_only_new_text_and_clears_ephemeral_payload(self):
        result=[];chunks=[]
        def invoke():result.append(self.broker.transport({'provider_id':'p','model':'fixture','prompt':'test','on_text':chunks.append},timeout=3))
        thread=threading.Thread(target=invoke);thread.start();job=None
        for _ in range(30):
            job=self.broker.poll(['fixture'])
            if job:break
            time.sleep(.02)
        self.assertIsNotNone(job)
        self.broker.append(job['id'],job['lease'],1,'Hi');time.sleep(.08)
        self.broker.append(job['id'],job['lease'],2,' there',True);thread.join(2)
        self.assertFalse(thread.is_alive());self.assertEqual(result[0]['text'],'Hi there');self.assertEqual(''.join(chunks),'Hi there')
        row=self.store.one('SELECT prompt,content FROM inference_jobs WHERE id=?',(job['id'],));self.assertEqual(row,{'prompt':'','content':''})
    def test_consumer_cancellation_closes_job_and_refuses_late_completion(self):
        stop=threading.Event();errors=[]
        def invoke():
            try:self.broker.transport({'provider_id':'p','model':'fixture','prompt':'test','stop_check':stop.is_set},timeout=3)
            except inference.ProviderTransportError as error:errors.append(str(error))
        thread=threading.Thread(target=invoke);thread.start();job=None
        for _ in range(30):
            job=self.broker.poll(['fixture'])
            if job:break
            time.sleep(.02)
        self.assertIsNotNone(job);stop.set();thread.join(2)
        self.assertTrue(errors);self.assertEqual(self.broker.heartbeat(job['id'],job['lease'])['status'],'cancelled')
        with self.assertRaises(ValueError):self.broker.append(job['id'],job['lease'],1,'late',True)


class WorkerBoundaryTests(unittest.TestCase):
    def test_backend_and_ollama_url_policies(self):
        for value in ('http://public.example','https://public.example','http://host.example.ts.net','https://u:p@host.ts.net','https://host.ts.net/path','http://0.0.0.0:8787'):
            with self.assertRaises(mac_worker.WorkerError):mac_worker.backend_url(value)
        mac_worker.backend_url('https://backend.example.ts.net')
        for value in ('http://100.100.100.100:11434','https://mac.example.ts.net','http://127.0.0.1:11434/api/pull'):
            with self.assertRaises(mac_worker.WorkerError):mac_worker.local_ollama(value)
        mac_worker.local_ollama('http://127.0.0.1:11434')
    def test_job_cannot_add_urls_commands_or_uninstalled_models(self):
        class Client:
            def request(self,path,payload):return {'job':{'url':'https://evil.example','prompt':'x'}}
        worker=mac_worker.Worker(Client(),['fixture'])
        with patch.object(mac_worker.providers,'discover_models',return_value=['fixture']):
            with self.assertRaisesRegex(mac_worker.WorkerError,'schema'):worker.poll_once()
    def test_token_loader_refuses_nonprivate_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'token';path.write_text('synthetic-worker-token-'+'x'*32);path.chmod(0o644)
            with self.assertRaises(mac_worker.WorkerError):mac_worker.read_token(path)
            path.chmod(0o600);self.assertTrue(mac_worker.read_token(path))
            link=Path(directory)/'link';link.symlink_to(path)
            with self.assertRaises(mac_worker.WorkerError):mac_worker.read_token(link)


@unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS')=='1','requires explicitly enabled loopback listener')
class WorkerHttpTests(unittest.TestCase):
    request=fixture.AuthHttpTests.request
    def setUp(self):
        fixture.AuthHttpTests.setUp(self)
        self.old_worker=server.WORKER_AUTH;self.worker_token='synthetic-worker-only-'+'y'*32
        server.WORKER_AUTH=security.OwnerAuth(self.worker_token)
        self.owner={'Authorization':'Bearer '+self.token};self.worker={'Authorization':'Bearer '+self.worker_token}
    def tearDown(self):
        server.WORKER_AUTH=self.old_worker;fixture.AuthHttpTests.tearDown(self)
    def call(self,path,data=None,worker=False,method='POST'):
        status,_,body=self.request(method,path,data,self.worker if worker else self.owner)
        return status,json.loads(body)
    def test_scoped_worker_has_no_owner_authority_and_owner_cannot_claim(self):
        self.assertEqual(self.call('/api/worker/poll',{'models':['fixture']})[0],401)
        self.assertEqual(self.call('/api/worker/poll',{'models':['fixture']},True)[0],200)
        for method,path,payload in [('GET','/api/projects',None),('GET','/api/diagnostics',None),('POST','/api/approvals',{}),('PATCH','/api/approvals/x',{}),('POST','/api/session',{'token':self.token})]:
            self.assertEqual(self.call(path,payload,True,method)[0],403)
        self.assertEqual(self.call('/api/worker/poll',{'models':[],'endpoint':'https://evil.example'},True)[0],409)
    def test_real_http_chat_uses_worker_chunks_without_granting_tool_access(self):
        _,provider=self.call('/api/providers',{'kind':'mac-worker','model':'fixture'})
        self.call('/api/worker/poll',{'models':['fixture']},True)
        _,chat=self.call('/api/conversations',{'provider_id':provider['id'],'model':'fixture'})
        _,turn=self.call('/api/conversations/'+chat['id']+'/messages',{'content':'synthetic request'})
        job=None
        for _ in range(40):
            _,response=self.call('/api/worker/poll',{'models':['fixture']},True);job=response['job']
            if job:break
            time.sleep(.02)
        self.assertIsNotNone(job);self.assertNotIn('endpoint',job)
        self.assertEqual(self.call('/api/worker/jobs/'+job['id']+'/chunks',{'lease':'wrong','seq':1,'text':'x'},True)[0],403)
        self.call('/api/worker/jobs/'+job['id']+'/chunks',{'lease':job['lease'],'seq':1,'text':'hello worker','done':True},True)
        final=conversations.wait_for_message(server.STORE,turn['assistant_message_id'],timeout=3)
        self.assertEqual(final['status'],'complete');self.assertEqual(final['content'],'hello worker')
        status,_,raw=self.request('GET',f"/api/conversations/{chat['id']}/messages/{final['id']}/stream",headers=self.owner)
        self.assertEqual(status,200);self.assertIn(b'event: done',raw);self.assertIn(b'hello worker',raw)
    def test_mac_provider_cannot_smuggle_endpoint_or_cloud_flag(self):
        for extra in ({'endpoint':'http://evil.example'},{'cloud_allowed':True},{'secret_ref':'CLOUD_KEY'}):
            self.assertEqual(self.call('/api/providers',{'kind':'mac-worker','model':'fixture',**extra})[0],400)
