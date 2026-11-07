"""Worker replay, malformed peer responses, hot rotation and stale-authority races."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from app import mac_worker,worker_state,inference,security,server
import test_inference as fixtures


def job():
    return {'id':str(uuid.uuid4()),'model':'fixture','prompt':'synthetic prompt','prompt_sha256':hashlib.sha256(b'synthetic prompt').hexdigest(),'deadline':int(time.time())+120,'lease':'l'*48}


class Peer:
    def __init__(self,value):self.job=value;self.malformed_ack=False
    def request(self,path,body):
        if path.endswith('/poll'):return {'job':self.job}
        if path.endswith('/heartbeat'):return {'status':'running','seq':0,'deadline':self.job['deadline']}
        if self.malformed_ack:return {'status':'complete','seq':False,'duplicate':False}
        return {'status':'failed' if body.get('error') else 'complete' if body.get('done') else 'running','seq':body['seq'],'duplicate':False}


class ReplayTests(unittest.TestCase):
    def test_claim_survives_restart_before_any_result_and_prevents_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve();path.chmod(0o700)
            journal=worker_state.ReplayJournal(path);value=job();journal.claim(value);journal.close()
            journal=worker_state.ReplayJournal(path)
            try:
                with self.assertRaisesRegex(worker_state.ReplayError,'already claimed'):journal.claim(value)
                self.assertEqual(journal.connection.execute('SELECT status FROM claims').fetchone()[0],'claimed')
                self.assertNotIn('synthetic prompt',repr(journal.connection.execute('SELECT * FROM claims').fetchall()))
            finally:journal.close()
    def test_two_process_connections_cannot_claim_the_same_id_and_budget_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve();path.chmod(0o700)
            one=worker_state.ReplayJournal(path);two=worker_state.ReplayJournal(path);value=job()
            try:
                one.claim(value)
                with self.assertRaises(worker_state.ReplayError):two.claim(value)
                with patch.object(worker_state,'MAX_CLAIMS',1):
                    with self.assertRaisesRegex(worker_state.ReplayError,'budget'):two.claim(job())
            finally:one.close();two.close()
    def test_state_refuses_shared_directories_symlinks_and_hardlink_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve();path.chmod(0o755)
            with self.assertRaises(worker_state.ReplayError):worker_state.ReplayJournal(path)
            path.chmod(0o700);value=worker_state.ReplayJournal(path);value.close()
            os.link(path/'inference-claims.sqlite3',path/'alias')
            with self.assertRaises(worker_state.ReplayError):worker_state.ReplayJournal(path)
    def test_ambiguous_completion_is_not_inferred_again_even_after_peer_replays(self):
        peer=Peer(job());peer.malformed_ack=True;calls=[]
        def adapter(request):calls.append(True);request['on_text']('answer');return {'text':'answer'}
        journal=worker_state.ReplayJournal();worker=mac_worker.Worker(peer,['fixture'],adapter=adapter,journal=journal)
        try:
            with patch.object(mac_worker.providers,'discover_models',return_value=['fixture']):
                with self.assertRaises(mac_worker.WorkerError):worker.poll_once()
                with self.assertRaisesRegex(mac_worker.WorkerError,'already claimed'):worker.poll_once()
            self.assertEqual(len(calls),1)
            self.assertEqual(journal.connection.execute('SELECT status FROM claims').fetchone()[0],'failed')
        finally:journal.close()
    def test_invalid_uuid_types_and_unknown_poll_fields_never_invoke(self):
        for value in (123456789012345678901234567890123456,'-'*36,str(uuid.uuid1())):
            item=job();item['id']=value;peer=Peer(item);worker=mac_worker.Worker(peer,['fixture'],adapter=lambda _:self.fail('must not invoke'))
            try:
                with patch.object(mac_worker.providers,'discover_models',return_value=['fixture']):
                    with self.assertRaises(mac_worker.WorkerError):worker.poll_once()
            finally:worker.journal.close()
        class Bad:
            def request(self,*_):return {'job':None,'extra':'ignored?'}
        worker=mac_worker.Worker(Bad(),['fixture'])
        try:
            with patch.object(mac_worker.providers,'discover_models',return_value=['fixture']):
                with self.assertRaisesRegex(mac_worker.WorkerError,'schema'):worker.poll_once()
        finally:worker.journal.close()
    def test_duplicate_json_fields_are_rejected(self):
        for value in ('{"models":[],"models":["other"]}','{"job":{"id":"a","id":"b"}}'):
            with self.assertRaisesRegex(ValueError,'Duplicate'):json.loads(value,object_pairs_hook=security.unique_json_object)

    def test_main_server_database_aliases_are_refused_without_reading_or_modifying_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);outside=root/'untouched';outside.write_bytes(b'synthetic unrelated data');outside.chmod(0o600)
            data=root/'data';data.mkdir();alias=data/'personal_codex.db';os.link(outside,alias)
            with patch.object(server,'DATA',data),patch.object(server,'DB_PATH',alias):
                with self.assertRaisesRegex(ValueError,'hardlink'):server.Store()
            self.assertEqual(outside.read_bytes(),b'synthetic unrelated data')



@unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS')=='1','requires explicitly enabled loopback listener')
class RotationHttpTests(unittest.TestCase):
    setUp=fixtures.WorkerHttpTests.setUp
    tearDown=fixtures.WorkerHttpTests.tearDown
    request=fixtures.WorkerHttpTests.request
    call=fixtures.WorkerHttpTests.call
    def private_token(self,value):
        path=server.DATA/'new-worker-token';path.write_text(value);path.chmod(0o600);return path
    def test_rotation_revokes_inflight_jobs_old_credential_and_old_lease_without_replay(self):
        _,provider=self.call('/api/providers',{'kind':'mac-worker','model':'fixture'})
        self.call('/api/worker/poll',{'models':['fixture']},True)
        broker=inference.Broker(server.STORE);jid=broker.submit(provider['id'],'fixture','test');leased=broker.poll(['fixture'])
        candidate='new-worker-only-'+'z'*48;path=self.private_token(candidate)
        with patch.dict(os.environ,{'PERSONAL_CODEX_WORKER_TOKEN_FILE':str(path)}):
            status,body=self.call('/api/inference/reload-credential',{'confirm':True})
        self.assertEqual(status,200);self.assertEqual(body,{'rotated':True,'interrupted_jobs':1})
        self.assertEqual(self.call('/api/worker/poll',{'models':[]},True)[0],401)
        self.assertEqual(broker.catalog()['online'],False)
        self.assertEqual(server.STORE.one('SELECT status,prompt,content,lease_hash FROM inference_jobs WHERE id=?',(jid,)),{'status':'interrupted','prompt':'','content':'','lease_hash':None})
        client=mac_worker.Client(f'http://127.0.0.1:{self.http.server_port}',candidate)
        self.assertIsNone(client.request('/api/worker/poll',{'models':['fixture']})['job'])
        with self.assertRaises(PermissionError):broker.heartbeat(jid,leased['lease'])
    def test_invalid_owner_or_shared_candidate_keeps_current_worker_authority(self):
        for candidate,mode in [(self.token,0o600),('valid-candidate-'+'a'*48,0o644),('',0o600)]:
            path=self.private_token(candidate);path.chmod(mode)
            with patch.dict(os.environ,{'PERSONAL_CODEX_WORKER_TOKEN_FILE':str(path)}):
                self.assertEqual(self.call('/api/inference/reload-credential',{'confirm':True})[0],409)
            self.assertEqual(self.call('/api/worker/poll',{'models':[]},True)[0],200)
        self.assertEqual(self.call('/api/inference/reload-credential',{'confirm':True},True)[0],403)
        self.assertEqual(self.call('/api/inference/reload-credential',{})[0],400)
    def test_same_credential_is_noop_and_worker_client_rereads_atomic_replacement(self):
        path=self.private_token(self.worker_token)
        client=mac_worker.Client(f'http://127.0.0.1:{self.http.server_port}',self.worker_token,token_file=path)
        with patch.dict(os.environ,{'PERSONAL_CODEX_WORKER_TOKEN_FILE':str(path)}):
            self.assertEqual(self.call('/api/inference/reload-credential',{'confirm':True})[1]['rotated'],False)
            replacement=path.with_name('replacement');replacement.write_text('rotated-worker-'+'b'*48);replacement.chmod(0o600);replacement.replace(path)
            self.assertTrue(self.call('/api/inference/reload-credential',{'confirm':True})[1]['rotated'])
        self.assertIsNone(client.request('/api/worker/poll',{'models':['fixture']})['job'])
    def test_old_authority_checked_again_after_slow_body_and_rotation(self):
        candidate='replacement-worker-'+'c'*48;path=self.private_token(candidate)
        body=b'{"models":["fixture"]}';connection=socket.create_connection(('127.0.0.1',self.http.server_port),timeout=3)
        try:
            header=(f'POST /api/worker/poll HTTP/1.1\r\nHost: 127.0.0.1:{self.http.server_port}\r\nAuthorization: Bearer {self.worker_token}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n').encode()
            connection.sendall(header);time.sleep(.05)
            with patch.dict(os.environ,{'PERSONAL_CODEX_WORKER_TOKEN_FILE':str(path)}):
                self.assertTrue(self.call('/api/inference/reload-credential',{'confirm':True})[1]['rotated'])
            connection.sendall(body);response=http.client.HTTPResponse(connection);response.begin()
            self.assertEqual(response.status,401);response.read();response.close()
        finally:connection.close()
        self.assertFalse(inference.Broker(server.STORE).catalog()['online'])
