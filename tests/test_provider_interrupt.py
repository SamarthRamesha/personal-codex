import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from app import providers


@unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS')=='1','requires explicitly enabled loopback listener')
class SilentProviderCancellationTests(unittest.TestCase):
    def setUp(self):
        self.release=threading.Event();release=self.release
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length','0')))
                self.send_response(200);self.send_header('Content-Type','text/event-stream' if self.path.endswith('/chat/completions') else 'application/x-ndjson');self.end_headers()
                line=('data: '+json.dumps({'choices':[{'delta':{'content':'partial'}}]})+'\n\n' if self.path.endswith('/chat/completions') else json.dumps({'message':{'content':'partial'},'done':False})+'\n')
                self.wfile.write(line.encode());self.wfile.flush();release.wait(8)
            def log_message(self,*args):pass
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.endpoint=f'http://127.0.0.1:{self.http.server_port}'
    def tearDown(self):
        self.release.set();self.http.shutdown();self.http.server_close();self.thread.join()
    def check_cancel(self,adapter):
        stop=threading.Event();timer=threading.Timer(.3,stop.set);timer.start();chunks=[];started=time.monotonic()
        try:
            with self.assertRaises(providers.ProviderTransportError):
                adapter({'endpoint':self.endpoint,'model':'fixture','prompt':'synthetic','on_text':chunks.append,'stop_check':stop.is_set})
        finally:timer.cancel()
        self.assertLess(time.monotonic()-started,2,'silent reads must be interrupted before socket timeout')
        self.assertEqual(''.join(chunks),'partial')
    def test_ollama_silent_read_cancels_and_never_returns_partial_proposal(self):self.check_cancel(providers.OllamaStreamTransport(timeout=20))
    def test_openai_silent_read_cancels_and_never_returns_partial_proposal(self):self.check_cancel(providers.OpenAIStreamTransport('',timeout=20))
    def test_total_stream_deadline_is_bounded(self):
        started=time.monotonic()
        with self.assertRaises(providers.ProviderTransportError):
            providers.OllamaStreamTransport(timeout=.4)({'endpoint':self.endpoint,'model':'fixture','prompt':'synthetic'})
        self.assertLess(time.monotonic()-started,2)
