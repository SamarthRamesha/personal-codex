"""Actual loopback auth/TLS failure; never claimed as remote HTTPS or full acceptance."""
import importlib.util
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from app import server
from scripts import check_deployment
import test_inference as fixtures


class AcceptancePolicyTests(unittest.TestCase):
    def test_production_checker_refuses_loopback_and_public_or_insecure_destinations(self):
        for url in ('http://127.0.0.1:8787','http://host.ts.net','https://public.example','https://user:pass@host.ts.net'):
            with self.assertRaises(ValueError):check_deployment.Client(url)
        client=check_deployment.Client('https://backend.example.ts.net')
        with self.assertRaises(ValueError):client.get('/api/conversations/create')


@unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS')=='1','requires explicitly enabled loopback listener')
class AcceptanceHttpTests(unittest.TestCase):
    setUp=fixtures.WorkerHttpTests.setUp
    tearDown=fixtures.WorkerHttpTests.tearDown
    request=fixtures.WorkerHttpTests.request
    call=fixtures.WorkerHttpTests.call
    def test_readonly_checker_verifies_authorities_and_does_not_invoke_or_mutate(self):
        self.call('/api/worker/poll',{'models':['fixture']},True)
        client=check_deployment.Client(f'http://127.0.0.1:{self.http.server_port}',allow_loopback=True)
        with patch.dict(os.environ,{'PERSONAL_CODEX_EXECUTION_MODE':'disabled','PERSONAL_CODEX_RESERVE_GB':'1','PERSONAL_CODEX_STORAGE_ENFORCE':'1'}):
            result=check_deployment.assess(client,self.token,self.worker_token,'fixture')
        self.assertFalse(result['checks']['private_https']);self.assertFalse(result['http_acceptance_passed'])
        self.assertTrue(result['checks']['owner_authenticated']);self.assertTrue(result['checks']['coding_disabled'])
        self.assertTrue(result['checks']['worker_has_no_owner_authority']);self.assertTrue(result['checks']['owner_has_no_worker_authority'])
        self.assertFalse(result['mutations']);self.assertFalse(result['remote_acceptance_complete'])
        self.assertEqual(server.STORE.one('SELECT COUNT(*) AS n FROM inference_jobs')['n'],0)
        self.assertEqual(server.STORE.one('SELECT COUNT(*) AS n FROM conversations')['n'],0)
    @unittest.skipUnless(shutil.which('openssl'),'requires existing OpenSSL for disposable self-signed fixture')
    def test_self_signed_tls_is_rejected_before_owner_credential_or_request_is_sent(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):seen.append(True);self.send_error(500)
            def log_message(self,*_):pass
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);key=root/'server.key';cert=root/'cert.pem'
            subprocess.run([shutil.which('openssl'),'req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:P-256','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1'],check=True,capture_output=True,timeout=5);key.chmod(0o600)
            http=ThreadingHTTPServer(('127.0.0.1',0),Handler);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key);http.socket=context.wrap_socket(http.socket,server_side=True)
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            try:
                client=check_deployment.Client(f'https://127.0.0.1:{http.server_port}',allow_loopback=True)
                with self.assertRaises(check_deployment.CheckError):client.get('/api/connection',self.token)
                self.assertEqual(seen,[])
            finally:http.shutdown();http.server_close();thread.join()
