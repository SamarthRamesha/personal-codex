"""Durable, bounded inference mailbox for an outbound-only Mac worker.

No backend connection to a Mac port, arbitrary URL forwarding, cloud routing or tool authority.
Only an owner-approved provider/chat path submits work. A separate worker principal can claim
one lease, append ordered chunks and report installed model identifiers. Jobs never replay.
"""
from __future__ import annotations
import hashlib
import json
import re
import secrets
import time
import uuid

try:
    from providers import ProviderTransportError, redact_provider_text
except ImportError:
    from app.providers import ProviderTransportError, redact_provider_text

KIND = 'mac-worker'
MAX_JOBS = 4
MAX_RETAINED = 10_000
MAX_PROMPT = 100_000
MAX_RESPONSE = 200_000
MAX_CHUNK = 4_000
MAX_SEQUENCE = 4096
LEASE_SECONDS = 15
WORKER_TTL = 30
SCHEMA = """
CREATE TABLE IF NOT EXISTS inference_workers (
 id TEXT PRIMARY KEY, models TEXT NOT NULL, last_seen INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS inference_jobs (
 id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, model TEXT NOT NULL, prompt TEXT NOT NULL,
 prompt_sha256 TEXT NOT NULL, status TEXT NOT NULL, lease_hash TEXT, lease_until INTEGER,
 deadline INTEGER NOT NULL, seq INTEGER NOT NULL DEFAULT 0, content TEXT NOT NULL DEFAULT '',
 chunk_sha256 TEXT, error TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_inference_status ON inference_jobs(status,created_at);
"""


def now(): return int(time.time())
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def model_names(value):
    if not isinstance(value,list) or len(value)>32: raise ValueError('models must be a list of at most 32 identifiers')
    if any(not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}',name) for name in value):
        raise ValueError('Invalid installed model identifier')
    return sorted(set(value))


def recover(connection):
    connection.execute("UPDATE inference_jobs SET status='interrupted',prompt='',content='',lease_hash=NULL,error=? WHERE status IN ('queued','running')",
                       ('Backend restarted; inference was not replayed',))
    connection.execute('UPDATE inference_workers SET last_seen=0')


class Broker:
    def __init__(self, store): self.store=store

    def _expire(self):
        stamp=now()
        self.store.conn.execute("UPDATE inference_jobs SET status='expired',prompt='',lease_hash=NULL,error=?,updated_at=? "
                                "WHERE status IN ('queued','running') AND (deadline<=? OR (status='running' AND lease_until<=?))",
                                ('Inference deadline or worker lease expired; request a fresh invocation',stamp,stamp,stamp))

    def revoke_worker(self):
        with self.store.lock:
            cursor=self.store.conn.execute("UPDATE inference_jobs SET status='interrupted',prompt='',content='',lease_hash=NULL,error=?,updated_at=? WHERE status IN ('queued','running')",
                                           ('Worker credential rotated; inference not replayed',now()))
            self.store.conn.execute('UPDATE inference_workers SET last_seen=0')
            self.store.conn.commit()
            return cursor.rowcount

    def catalog(self):
        row=self.store.one("SELECT models,last_seen FROM inference_workers WHERE id='mac'")
        online=bool(row and 0<=now()-row['last_seen']<WORKER_TTL)
        return {'online':online,'models':json.loads(row['models']) if online else [],
                'last_seen':row['last_seen'] if row else None,'location':'mac-local','inbound_listener':False}

    def status(self):
        with self.store.lock:
            self._expire();self.store.conn.commit()
            counts=self.store.rows('SELECT status,COUNT(*) AS count FROM inference_jobs GROUP BY status')
        return {'worker':self.catalog(),'jobs':{row['status']:row['count'] for row in counts},
                'max_active':MAX_JOBS,'max_retained':MAX_RETAINED,'lease_seconds':LEASE_SECONDS}

    def submit(self, provider_id, model, prompt, timeout=180):
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt.encode())>MAX_PROMPT:
            raise ProviderTransportError('Inference prompt is empty or exceeds its byte budget')
        with self.store.lock:
            catalog=self.catalog()
            if not catalog['online']:raise ProviderTransportError('Mac inference worker is offline; no fallback was attempted')
            if model not in catalog['models']:raise ProviderTransportError('Selected model is not reported installed by the Mac worker')
            row=self.store.one('SELECT enabled,kind FROM providers WHERE id=?',(provider_id,))
            if not row or not row['enabled'] or row['kind']!=KIND:raise ProviderTransportError('Enabled Mac-worker provider required')
            self._expire()
            count=self.store.conn.execute("SELECT COUNT(*) FROM inference_jobs WHERE status IN ('queued','running')").fetchone()[0]
            retained=self.store.conn.execute('SELECT COUNT(*) FROM inference_jobs').fetchone()[0]
            if count>=MAX_JOBS or retained>=MAX_RETAINED:
                self.store.conn.commit()
                raise ProviderTransportError('Inference queue/retention budget reached; no job was submitted')
            jid=str(uuid.uuid4());stamp=now();deadline=stamp+max(2,min(300,int(timeout)))
            self.store.conn.execute('INSERT INTO inference_jobs (id,provider_id,model,prompt,prompt_sha256,status,deadline,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                                    (jid,provider_id,model,prompt,digest(prompt),'queued',deadline,stamp,stamp))
            self.store.conn.commit()
        return jid

    def poll(self, models):
        models=model_names(models);stamp=now()
        with self.store.lock:
            self._expire()
            self.store.conn.execute("INSERT INTO inference_workers VALUES ('mac',?,?) ON CONFLICT(id) DO UPDATE SET models=excluded.models,last_seen=excluded.last_seen WHERE inference_workers.last_seen<=? OR inference_workers.models!=excluded.models OR inference_workers.last_seen>excluded.last_seen",(json.dumps(models),stamp,stamp-5))
            if self.store.one("SELECT id FROM inference_jobs WHERE status='running' LIMIT 1"):
                self.store.conn.commit();return None
            candidates=self.store.rows("SELECT * FROM inference_jobs WHERE status='queued' ORDER BY created_at,rowid LIMIT ?",(MAX_JOBS,))
            row=next((job for job in candidates if job['model'] in models),None)
            if not row:self.store.conn.commit();return None
            lease=secrets.token_urlsafe(32)
            claimed=self.store.conn.execute("UPDATE inference_jobs SET status='running',lease_hash=?,lease_until=?,updated_at=? WHERE id=? AND status='queued'",
                                            (digest(lease),min(stamp+LEASE_SECONDS,row['deadline']),stamp,row['id']))
            self.store.conn.commit()
            if claimed.rowcount!=1:return None
            return {key:row[key] for key in ('id','model','prompt','prompt_sha256','deadline')} | {'lease':lease}

    def _leased(self,jid,lease):
        if not isinstance(lease,str) or len(lease)>128:raise PermissionError('Invalid inference lease')
        row=self.store.one('SELECT * FROM inference_jobs WHERE id=?',(jid,))
        if not row or not row['lease_hash'] or not secrets.compare_digest(row['lease_hash'],digest(lease)):
            raise PermissionError('Invalid inference lease')
        return row

    def heartbeat(self,jid,lease):
        with self.store.lock:
            self._expire();self.store.conn.commit()
            row=self._leased(jid,lease)
            stamp=now()
            if row['status']=='running':
                self.store.conn.execute('UPDATE inference_jobs SET lease_until=?,updated_at=? WHERE id=?',
                                        (min(stamp+LEASE_SECONDS,row['deadline']),stamp,jid))
            self.store.conn.execute("UPDATE inference_workers SET last_seen=? WHERE id='mac'",(stamp,))
            self.store.conn.commit()
            return {'status':row['status'],'seq':row['seq'],'deadline':row['deadline']}

    def append(self,jid,lease,seq,text='',done=False,error=''):
        if (isinstance(seq,bool) or not isinstance(seq,int) or not 1<=seq<=MAX_SEQUENCE or not isinstance(text,str) or len(text)>MAX_CHUNK
                or not isinstance(done,bool) or not isinstance(error,str) or len(error)>400):raise ValueError('Invalid inference chunk')
        if not text and not done and not error:raise ValueError('Empty nonterminal chunk refused; use heartbeat')
        if error and (text or done):raise ValueError('Error chunks cannot contain text or completion')
        payload=digest(json.dumps({'seq':seq,'text':text,'done':done,'error':error},sort_keys=True))
        with self.store.lock:
            self._expire();self.store.conn.commit();row=self._leased(jid,lease)
            if seq==row['seq'] and payload==row['chunk_sha256']:
                return {'status':row['status'],'seq':seq,'duplicate':True}
            if row['status']!='running' or seq!=row['seq']+1:raise ValueError('Inference chunk is stale or out of sequence')
            if len(row['content'].encode())+len(text.encode())>MAX_RESPONSE:raise ValueError('Inference response byte budget exceeded')
            status='failed' if error else 'complete' if done else 'running'
            if done and not (row['content']+text).strip():raise ValueError('Empty inference cannot complete')
            self.store.conn.execute('UPDATE inference_jobs SET seq=?,content=content||?,chunk_sha256=?,status=?,error=?,prompt=?,lease_until=?,updated_at=? WHERE id=?',
                                    (seq,text,payload,status,redact_provider_text(error)[:240] or None,
                                     '' if status!='running' else row['prompt'],min(now()+LEASE_SECONDS,row['deadline']),now(),jid))
            self.store.conn.commit()
            return {'status':status,'seq':seq,'duplicate':False}

    def cancel(self,jid,reason='Inference cancelled'):
        self.store.write("UPDATE inference_jobs SET status='cancelled',prompt='',error=?,updated_at=? WHERE id=? AND status IN ('queued','running')",
                         (reason[:240],now(),jid))

    def transport(self,request,timeout=180):
        stop=request.get('stop_check') or (lambda:False)
        on_text=request.get('on_text') or (lambda text:None)
        if stop():raise ProviderTransportError('Inference cancelled before submission')
        jid=self.submit(request.get('provider_id'),request.get('model'),request.get('prompt'),timeout)
        offset=0;deadline=time.monotonic()+max(2,min(300,int(timeout)))
        try:
            while True:
                if time.monotonic()>=deadline:
                    self.cancel(jid,'Consumer total deadline exceeded');raise ProviderTransportError('Mac inference total deadline exceeded')
                if stop():self.cancel(jid);raise ProviderTransportError('Mac inference cancelled')
                with self.store.lock:
                    self._expire();self.store.conn.commit();row=self.store.one('SELECT * FROM inference_jobs WHERE id=?',(jid,))
                content=row['content']
                if len(content)>offset:on_text(content[offset:]);offset=len(content)
                if row['status']=='complete':return {'text':content,'model':row['model'],'streamed':True,'inference_job_id':jid}
                if row['status'] not in ('queued','running'):raise ProviderTransportError(row['error'] or 'Mac inference did not complete')
                time.sleep(.05)
        except Exception:
            self.cancel(jid,'Inference consumer stopped; partial text is display-only')
            raise
        finally:
            # Ephemeral inference payload is not conversation history; retain only its digest/status.
            self.store.write("UPDATE inference_jobs SET prompt='',content='' WHERE id=? AND status NOT IN ('queued','running')",(jid,))
