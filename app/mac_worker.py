"""Outbound-only worker: private HTTPS control plane ↔ fixed loopback Ollama.

This process has no inbound listener, shell, project filesystem API or model-download route.
It accepts only an explicit installed-model allowlist and a distinct scoped worker credential.
"""
from __future__ import annotations
import argparse
import hashlib
import http.client
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import signal
import ssl
import sqlite3
import stat
import threading
import time
import uuid
from urllib.parse import urlsplit

try:
    from . import inference, providers, security, worker_state
except ImportError:
    import inference, providers, security, worker_state


class WorkerError(ValueError): pass


def backend_url(value):
    try:
        parsed=urlsplit(value);port=parsed.port
    except ValueError:raise WorkerError('Invalid backend URL') from None
    host=(parsed.hostname or '').lower()
    if (not host or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment
            or any(c.isspace() for c in value)):
        raise WorkerError('Backend URL must contain only scheme, host and port')
    if not ((security.is_loopback(host) and parsed.scheme in ('http','https'))
            or (host.endswith('.ts.net') and parsed.scheme=='https')):
        raise WorkerError('Worker requires loopback development or verified private HTTPS .ts.net backend')
    return parsed,host,port


def local_ollama(value):
    parsed,host,port=backend_url(value)
    if not security.is_loopback(host) or parsed.scheme!='http':
        raise WorkerError('Ollama must remain on a loopback HTTP endpoint')
    return value.rstrip('/')


def read_token(path):
    try:fd=os.open(Path(path).expanduser(),os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    except OSError:raise WorkerError('Worker token file unavailable or a symlink') from None
    with os.fdopen(fd,'r') as source:
        info=os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid!=os.getuid() or info.st_size>1024:
            raise WorkerError('Worker token file must be a private owner-only regular file')
        value=source.read(1025).strip()
    if not value:raise WorkerError('Worker token is empty')
    security.OwnerAuth(value)  # same validation, never logs/stores the value
    return value


class Client:
    def __init__(self,backend,token,timeout=5,token_file=None):
        self.parsed,self.host,self.port=backend_url(backend)
        security.OwnerAuth(token)
        if not token:raise WorkerError('Distinct worker credential required')
        self.token=token;self.timeout=timeout;self.token_file=token_file

    def request(self,path,payload):
        if not re.fullmatch(r'/api/worker/(poll|jobs/[a-f0-9-]{36}/(heartbeat|chunks))',path):
            raise WorkerError('Worker API path is outside its scope')
        token=read_token(self.token_file) if self.token_file else self.token
        body=json.dumps(payload).encode()
        if len(body)>inference.MAX_PROMPT:raise WorkerError('Worker request exceeds budget')
        connection=(http.client.HTTPSConnection(self.host,self.port,timeout=self.timeout,context=ssl.create_default_context())
                    if self.parsed.scheme=='https' else http.client.HTTPConnection(self.host,self.port,timeout=self.timeout))
        response=None
        guard=providers._StreamGuard(connection,lambda:False,self.timeout)
        try:
            connection.request('POST',path,body,{'Content-Type':'application/json','Authorization':'Bearer '+token,'Connection':'close'})
            guard.socket=connection.sock
            if guard.reason:raise WorkerError('Worker control deadline exceeded')
            response=connection.getresponse()
            limit=inference.MAX_PROMPT*6+16_000  # JSON escapes may expand one prompt byte sixfold.
            raw=response.read(limit)
            if guard.reason:raise WorkerError('Worker control connection exceeded its total deadline')
            if len(raw)>=limit:raise WorkerError('Worker response exceeds budget')
            if response.status!=200:raise WorkerError(f'Worker API rejected request (HTTP {response.status})')
            try:result=json.loads(raw,object_pairs_hook=security.unique_json_object)
            except (ValueError,UnicodeDecodeError):raise WorkerError('Worker API returned invalid JSON') from None
            if not isinstance(result,dict):raise WorkerError('Worker API returned an invalid object')
            return result
        except (OSError,TimeoutError,http.client.HTTPException):
            raise WorkerError('Worker control connection unavailable or TLS verification failed') from None
        finally:
            guard.close()
            if response is not None:response.close()
            connection.close()


class Worker:
    def __init__(self,client,models,ollama='http://127.0.0.1:11434',stop=None,adapter=None,journal=None):
        self.client=client;self.models=inference.model_names(models)
        if not self.models:raise WorkerError('Choose at least one explicit installed model')
        self.endpoint=local_ollama(ollama);self.stop=stop or threading.Event()
        self.adapter=adapter or providers.OllamaStreamTransport(timeout=180)
        self.journal=journal or worker_state.ReplayJournal()
        self._installed=[];self._discovered_at=0.0

    def poll_once(self):
        if time.monotonic()-self._discovered_at>=5:
            self._installed=providers.discover_models(self.endpoint,timeout=5);self._discovered_at=time.monotonic()
        allowed=[model for model in self.models if model in self._installed]
        result=self.client.request('/api/worker/poll',{'models':allowed})
        if not isinstance(result,dict) or set(result)!={'job'}:raise WorkerError('Invalid poll response schema')
        job=result['job']
        if job is None:return False
        if not isinstance(job,dict) or set(job)!={'id','model','prompt','prompt_sha256','deadline','lease'}:
            raise WorkerError('Invalid inference job schema')
        if (not isinstance(job['id'],str) or not re.fullmatch(r'[a-f0-9-]{36}',job['id']) or job['model'] not in allowed
                or not isinstance(job['prompt'],str) or len(job['prompt'].encode())>inference.MAX_PROMPT
                or hashlib.sha256(job['prompt'].encode()).hexdigest()!=job['prompt_sha256']
                or not isinstance(job['lease'],str) or not 32<=len(job['lease'])<=128
                or isinstance(job['deadline'],bool) or not isinstance(job['deadline'],int)
                or not time.time()-1<job['deadline']<=time.time()+301):
            raise WorkerError('Inference job failed model, digest, lease or deadline validation')
        try:
            if str(uuid.UUID(job['id'],version=4))!=job['id']:raise ValueError('Invalid job UUID')
            self.journal.claim(job)
        except (ValueError,sqlite3.Error) as error:raise WorkerError(str(error)) from None
        try:self._execute(job)
        except Exception:
            self.journal.finish(job['id'],'failed');raise
        else:self.journal.finish(job['id'],'complete')
        return True

    def _execute(self,job):
        path=f"/api/worker/jobs/{job['id']}";seq=0;buffer=[];last_flush=time.monotonic();cancel=threading.Event()
        heartbeat_done=threading.Event();text_digest=hashlib.sha256();text_bytes=0

        def heartbeat():
            while not heartbeat_done.wait(.5):
                if self.stop.is_set() or time.time()>=job['deadline']:
                    cancel.set();return
                try:
                    result=self.client.request(path+'/heartbeat',{'lease':job['lease']})
                    if (not isinstance(result,dict) or set(result)!={'status','seq','deadline'}
                            or result['status']!='running' or type(result['seq']) is not int
                            or not 0<=result['seq']<=inference.MAX_SEQUENCE or result['deadline']!=job['deadline']):cancel.set();return
                except WorkerError:cancel.set();return

        monitor=threading.Thread(target=heartbeat,name='inference-lease',daemon=True);monitor.start()

        def post_chunk(text='',done=False,error=''):
            nonlocal seq
            seq+=1
            payload={'lease':job['lease'],'seq':seq,'text':text,'done':done,'error':error}
            # Identical last-sequence append is idempotent. No inference invocation is retried.
            for attempt in range(3):
                try:
                    ack=self.client.request(path+'/chunks',payload)
                    expected='failed' if error else 'complete' if done else 'running'
                    if (set(ack)!={'status','seq','duplicate'} or ack['status']!=expected
                            or type(ack['seq']) is not int or ack['seq']!=seq or type(ack['duplicate']) is not bool):
                        raise WorkerError('Invalid inference append acknowledgment')
                    return ack
                except WorkerError:
                    if attempt==2:raise
                    if self.stop.wait(.1*(2**attempt)):raise WorkerError('Worker stopping')

        def flush(done=False):
            nonlocal last_flush
            text=''.join(buffer);buffer.clear();last_flush=time.monotonic()
            while len(text)>inference.MAX_CHUNK:
                post_chunk(text[:inference.MAX_CHUNK]);text=text[inference.MAX_CHUNK:]
            if text or done:post_chunk(text,done=done)

        def on_text(text):
            nonlocal text_bytes
            text_bytes+=len(text.encode())
            if text_bytes>inference.MAX_RESPONSE:raise WorkerError('Local response exceeds its byte budget')
            text_digest.update(text.encode())
            if cancel.is_set() or self.stop.is_set():raise WorkerError('Inference cancelled')
            buffer.append(text)
            if sum(map(len,buffer))>=512 or time.monotonic()-last_flush>=.2:flush()

        try:
            result=self.adapter({'endpoint':self.endpoint,'model':job['model'],'prompt':job['prompt'],
                                 'cloud_allowed':False,'on_text':on_text,'stop_check':lambda:cancel.is_set() or self.stop.is_set()})
            if cancel.is_set() or self.stop.is_set():raise WorkerError('Inference cancelled')
            if not isinstance(result,dict) or not str(result.get('text','')).strip():raise WorkerError('Ollama produced no completed text')
            if hashlib.sha256(result['text'].encode()).digest()!=text_digest.digest():
                raise WorkerError('Completed text differs from streamed text')
            flush(done=True)
        except Exception as error:
            if not cancel.is_set():
                try:post_chunk(error=providers.redact_provider_text(str(error))[:240] or 'Local inference failed')
                except WorkerError:pass
            raise WorkerError('Local inference failed or was cancelled; no completed response published') from None
        finally:
            heartbeat_done.set();monitor.join(timeout=6)


class PrivateRotatingHandler(RotatingFileHandler):
    def _open(self):
        fd=os.open(self.baseFilename,os.O_WRONLY|os.O_APPEND|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
        return os.fdopen(fd,'a',encoding=self.encoding,errors=self.errors)


def worker_logger(path=None):
    logger=logging.getLogger('personal_codex.mac_worker');logger.setLevel(logging.INFO);logger.propagate=False
    for old in list(logger.handlers):old.close();logger.removeHandler(old)
    if path:
        target=Path(path).expanduser().absolute();parent=target.parent
        info=parent.stat()
        if parent.is_symlink() or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
            raise WorkerError('Worker log needs an existing owner-only 0700 directory')
        fd=os.open(target,os.O_WRONLY|os.O_APPEND|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600:
                raise WorkerError('Worker log must be an owner-only regular file')
        finally:os.close(fd)
        handler=PrivateRotatingHandler(target,maxBytes=262144,backupCount=2,encoding='utf-8')
    else:handler=logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'));logger.addHandler(handler)
    return logger


def main(argv=None):
    parser=argparse.ArgumentParser(description='Outbound-only private Mac Ollama worker; never opens a listener.')
    parser.add_argument('--backend',required=True)
    parser.add_argument('--token-file',required=True)
    parser.add_argument('--models',nargs='+',required=True)
    parser.add_argument('--ollama',default='http://127.0.0.1:11434')
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--state-dir',required=True,help='existing private 0700 directory for durable no-replay claims')
    parser.add_argument('--log-file',help='optional rotating log in an existing private 0700 directory')
    args=parser.parse_args(argv)
    stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    try:
        logger=worker_logger(args.log_file)
        journal=worker_state.ReplayJournal(args.state_dir)
        worker=Worker(Client(args.backend,read_token(args.token_file),token_file=args.token_file),args.models,args.ollama,stop=stop,journal=journal)
    except (ValueError,OSError,sqlite3.Error):parser.exit(2,'Worker configuration unavailable or unsafe; review URL, private credential and log metadata.\n')
    backoff=1
    while not stop.is_set():
        try:
            worker.poll_once();backoff=1
            if args.once:return 0
        except (WorkerError,providers.ProviderTransportError,sqlite3.Error):
            logger.warning('Mac worker unavailable or job failed; no fallback attempted')
            if args.once:return 2
            backoff=min(30,backoff*2)
        stop.wait(backoff)
    return 0


if __name__=='__main__':raise SystemExit(main())
