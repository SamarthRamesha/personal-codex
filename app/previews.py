"""Reviewed, read-only Node previews bound to one task and IPv4 loopback port."""
from __future__ import annotations
import http.client
import json
import os
from pathlib import Path
import re
import select
import shlex
import socket
import subprocess
import sys
import threading
import time
try:
    from . import local_runner, project_files, tools
except ImportError:
    import local_runner, project_files, tools


class Previews:
    def __init__(self, host):
        self.host, self.store = host, host.STORE
        self.lock, self.active = threading.RLock(), {}

    def workspace(self, task):
        h = self.host
        if not h.AUTH.enabled or not h.network_policy.offline_only():
            raise ValueError('Previews require authenticated local offline mode')
        h.require_execution()
        row = self.store.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'", (task,))
        if not row: raise ValueError('Approve a task worktree first')
        return h.safe_workspace_path(row)

    def snapshot(self, task, script, port):
        root = self.workspace(task)
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError('Choose a loopback port from 1024 to 65535')
        if not isinstance(script,str) or script not in {'dev', 'start', 'serve', 'preview'}:
            raise ValueError('Choose a declared development script')
        _, text = project_files.text_file(root, 'package.json')
        manifest = json.loads(text)
        if not isinstance(manifest,dict) or not isinstance(manifest.get('scripts'),dict):
            raise ValueError('Declare development scripts in package.json')
        command = manifest['scripts'].get(script)
        if not isinstance(command, str): raise ValueError('That development script is not declared')
        argv = shlex.split(command)
        if len(argv) != 2 or argv[0] != 'node' or not argv[1].endswith(('.js', '.mjs', '.cjs')):
            raise ValueError('Managed previews currently support declared scripts of the form node relative-entry.js')
        tools.resolve_in_workspace(root, argv[1])
        raw, _ = project_files.text_file(root, argv[1])
        info = root.stat()
        return {'root':str(root), 'identity':[info.st_dev, info.st_ino], 'script':script, 'port':port,
                'command':argv, 'hashes':{'package.json':project_files.digest(text.encode()), argv[1]:project_files.digest(raw)},
                'url':f'http://127.0.0.1:{port}', 'network':'One inherited app-owned loopback socket; new binds and outbound networking denied',
                'files':'Read the selected task worktree; write only private preview scratch/logs',
                'lifetime_seconds':900, 'environment':{'HOST':'127.0.0.1', 'PORT':str(port)}}

    def propose(self, task, script, port):
        with self.lock:
            if self.host.project_agent.running(task) or self.store.one("SELECT id FROM dependency_jobs WHERE task_id=? AND status='running'", (task,)):
                raise ValueError('Wait for coding or dependency installation before reviewing a preview')
            if task in self.active: raise ValueError('Stop the owned preview before reviewing another')
            proposal = self.snapshot(task, script, port)
            encoded = json.dumps(proposal, sort_keys=True)
            identifier, now = self.host.uid(), self.host.now()
            self.store.write('INSERT INTO preview_jobs VALUES (?,?,?,?,?,?,?,?,?)',
                             (identifier, task, encoded, project_files.digest(encoded.encode()), 'proposed', '', now, now+600, now))
            return self.get(task, identifier)

    def get(self, task, identifier=None):
        self.workspace(task)
        row = self.store.one('SELECT * FROM preview_jobs WHERE task_id=? ' +
                             ('AND id=?' if identifier else 'ORDER BY created_at DESC,rowid DESC LIMIT 1'),
                             (task,identifier) if identifier else (task,))
        if not row: return None
        result = {**row, 'proposal':json.loads(row['proposal']), 'logs':''}
        log = self.host.DATA / 'previews' / row['id'] / 'output.log'
        if log.is_file() and not log.is_symlink():
            with log.open('rb') as stream:
                stream.seek(max(0, os.fstat(stream.fileno()).st_size-16000))
                result['logs'] = self.host.redacted(stream.read(16000).decode('utf-8',errors='replace'))
        with self.lock:
            active = self.active.get(task)
            if active and active[0] == row['id']:
                result['process_id'] = active[2]
        return result

    @staticmethod
    def available(port):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))

    def execute(self, task, request):
        if set(request) != {'id','digest','confirm'} or request['confirm'] is not True:
            raise ValueError('Confirm the exact reviewed preview')
        with self.lock:
            row = self.get(task, request['id'])
            if not row or row['digest'] != request['digest'] or project_files.digest(json.dumps(row['proposal'],sort_keys=True).encode()) != row['digest']:
                raise ValueError('Preview proposal changed')
            if row['status'] != 'proposed' or row['expires_at'] <= self.host.now():
                raise ValueError('Preview approval expired or already used')
            if task in self.active: raise ValueError('Stop the owned preview before starting another')
            proposal = row['proposal']
            if proposal != self.snapshot(task, proposal['script'], proposal['port']):
                raise ValueError('Preview files or worktree changed; review a new proposal')
            self.available(proposal['port'])
            if self.host.project_agent.running(task) or self.store.one("SELECT id FROM dependency_jobs WHERE task_id=? AND status='running'", (task,)):
                raise ValueError('Wait for coding or dependency installation before starting a preview')
            local_runner.trusted_program('node')
            address = f'localhost:{proposal["port"]}'
            job = self.host.DATA / 'previews' / row['id']
            job.mkdir(mode=0o700, parents=True)
            bootstrap = Path(__file__).with_name('preview_bootstrap.cjs')
            launch = local_runner.sandboxed(['node', '--require', str(bootstrap), *proposal['command'][1:]],
                                            reads=(Path(proposal['root']),job,bootstrap), writes=(job,))
            launch[2] += f' (allow network-inbound (local ip "{address}")) (deny network-bind (local ip "*:*"))'
            with self.store.lock, self.store.conn:
                claim = self.store.conn.execute("UPDATE preview_jobs SET status='starting',updated_at=? WHERE id=? AND status='proposed'", (self.host.now(), row['id']))
                if claim.rowcount != 1: raise ValueError('Preview already claimed')
            reader, writer = os.pipe()
            process = None
            listener = socket.socket()
            try:
                listener.bind(('127.0.0.1', proposal['port']))
                listener.listen(128)
                env = {**local_runner.base_env(job), **proposal['environment'], 'TMPDIR':str(job), 'NODE_OPTIONS':'--max-old-space-size=512', 'PERSONAL_CODEX_LISTEN_FD':str(listener.fileno())}
                with (job / 'output.log').open('xb') as output:
                    process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('preview_supervisor.py')),
                        str(os.getpid()), str(writer), *launch], cwd=proposal['root'], env=env, stdout=output, stderr=subprocess.STDOUT,
                        start_new_session=True, pass_fds=(writer,listener.fileno()))
                os.close(writer);writer=-1
                if not select.select([reader],[],[],3)[0]: raise ValueError('Preview process identity was not returned')
                value = os.read(reader,64)
                if not re.fullmatch(rb'[0-9]+\n',value): raise ValueError('Preview could not start; inspect logs')
                child = int(value)
                cancelled = threading.Event()
                monitor = threading.Thread(target=self._monitor,args=(row,process,child,cancelled),daemon=True)
                self.active[task] = (row['id'],process,child,cancelled,monitor)
                monitor.start()
            except Exception:
                if process: self.host.terminate_process_group(process)
                self.store.write("UPDATE preview_jobs SET status='failed',output=? WHERE id=?", ('Preview startup failed; inspect logs',row['id']))
                raise
            finally:
                listener.close()
                os.close(reader)
                if writer>=0: os.close(writer)
        return self.get(task,row['id'])

    def owned_listener(self, child, port):
        result = subprocess.run(['/usr/sbin/lsof','-nP','-a','-g',str(child),'-iTCP:'+str(port),'-sTCP:LISTEN','-Fn'],
                                env={'PATH':os.defpath},capture_output=True,timeout=2)
        names = [line for line in result.stdout.decode(errors='replace').splitlines() if line.startswith('n')]
        return bool(names) and all(line == f'n127.0.0.1:{port}' for line in names)

    def _monitor(self,row,process,child,cancelled):
        status, detail, ready = 'failed','Preview exited; inspect logs',False
        started = time.monotonic()
        try:
            while process.poll() is None:
                if cancelled.is_set() or self.host.STOPPING.is_set():
                    status,detail='stopped','Owned preview stopped';break
                if not ready:
                    if time.monotonic()-started>12: raise ValueError('Preview did not become ready on its approved loopback port')
                    if self.owned_listener(child,row['proposal']['port']):
                        connection = http.client.HTTPConnection('127.0.0.1',row['proposal']['port'],timeout=.5)
                        try:
                            connection.request('GET','/')
                            response=connection.getresponse()
                            ready=200<=response.status<400 and self.owned_listener(child,row['proposal']['port'])
                        except OSError: pass
                        finally: connection.close()
                        if ready:
                            self.store.write("UPDATE preview_jobs SET status='running',output=?,updated_at=? WHERE id=?", ('Owned HTTP preview ready',self.host.now(),row['id']))
                time.sleep(.1)
        except Exception as error:
            detail=self.host.redacted(str(error))[:1000]
        finally:
            if process.poll() is not None and status != 'stopped':
                status = 'expired' if process.returncode == 130 else 'exited' if ready else 'failed'
                detail = 'Preview lifetime ended; review a new start' if status == 'expired' else f'Preview exited with status {process.returncode}; inspect logs'
            try: process.terminate()
            except ProcessLookupError: pass
            try: process.wait(timeout=4)
            except subprocess.TimeoutExpired: self.host.terminate_process_group(process)
            try:
                self.store.write('UPDATE preview_jobs SET status=?,output=?,updated_at=? WHERE id=?',(status,detail,self.host.now(),row['id']))
            finally:
                with self.lock: self.active.pop(row['task_id'],None)

    def stop(self,task):
        with self.lock:
            item=self.active.get(task)
            if item: item[3].set()
            return bool(item)

    def close(self):
        with self.lock:
            items=list(self.active.values())
            for item in items: item[3].set()
        for item in items: item[4].join(6)
        return all(not item[4].is_alive() for item in items)
