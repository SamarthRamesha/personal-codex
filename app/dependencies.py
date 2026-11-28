"""Reviewed npm lockfile installs. Download bytes through a fixed TLS origin;
run npm offline without lifecycle scripts, then publish only new node_modules.
No dependency command or URL is supplied by the model or execution request.
"""
from __future__ import annotations
import base64
import hashlib
import http.client
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import tarfile
import threading
import time
from urllib.parse import urlsplit

try:
    from . import local_runner, project_files
except ImportError:
    import local_runner, project_files

MAX_PACKAGES = 100
MAX_DOWNLOAD = 64 * 1024 * 1024
MAX_PACKAGE = 8 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
COMMAND = ['npm', 'ci', '--offline', '--ignore-scripts', '--no-audit', '--no-fund']


def manifests(root):
    result = {}
    for name in ('package.json', 'package-lock.json'):
        with project_files.parent_directory(root, name) as (parent, leaf):
            raw, _ = project_files.snapshot(parent, leaf)
        result[name] = raw
    return result


def package_plan(raw):
    manifest = json.loads(raw['package.json'])
    lock = json.loads(raw['package-lock.json'])
    if not isinstance(manifest, dict) or not isinstance(lock, dict) or lock.get('lockfileVersion') not in (2, 3):
        raise ValueError('Use a regular package.json and npm lockfile version 2 or 3')
    if manifest.get('workspaces'):
        raise ValueError('Workspace installs need a separately reviewed workflow')
    packages = lock.get('packages')
    if not isinstance(packages, dict) or len(packages) > MAX_PACKAGES + 1:
        raise ValueError('The reviewed installer supports at most 100 locked packages')
    result = []
    for path, item in packages.items():
        if path == '':
            continue
        if not isinstance(path, str) or not path.startswith('node_modules/') or '..' in path.split('/') or not isinstance(item, dict):
            raise ValueError('Unsupported locked package path')
        url, integrity = item.get('resolved'), item.get('integrity')
        if item.get('link') or not isinstance(url, str) or not isinstance(integrity, str):
            raise ValueError('Every package needs an exact registry tarball and SHA512 integrity')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'registry.npmjs.org' or parsed.query or parsed.fragment
                or not re.fullmatch(r'/[A-Za-z0-9@_./+-]+\.tgz', parsed.path) or '..' in parsed.path.split('/')):
            raise ValueError('Only exact HTTPS registry.npmjs.org tarballs are supported')
        try:
            expected = base64.b64decode(integrity.removeprefix('sha512-'), validate=True)
        except ValueError:
            raise ValueError('Invalid SHA512 package integrity') from None
        if not integrity.startswith('sha512-') or len(expected) != 64:
            raise ValueError('Every package requires a SHA512 digest')
        result.append({'path': path, 'version': str(item.get('version', ''))[:100], 'url': url, 'integrity': integrity})
    return sorted(result, key=lambda item: item['path'])


def download(package, stopped):
    connection = http.client.HTTPSConnection('registry.npmjs.org', timeout=10)
    try:
        connection.request('GET', urlsplit(package['url']).path, headers={'Accept': 'application/octet-stream'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('Package download failed; redirects and alternate origins are refused')
        content = bytearray()
        while not stopped():
            part = response.read(65536)
            if not part:
                break
            content.extend(part)
            if len(content) > MAX_PACKAGE:
                raise ValueError('Package exceeds the 8 MiB download limit')
        if stopped():
            raise ValueError('Installation cancelled')
    finally:
        connection.close()
    expected = package['integrity'].split('-', 1)[1]
    if base64.b64encode(hashlib.sha512(content).digest()).decode() != expected:
        raise ValueError('Downloaded package integrity did not match the reviewed lockfile')
    expanded = count = 0
    with tarfile.open(fileobj=io.BytesIO(content), mode='r|gz') as archive:
        for entry in archive:
            count += 1
            path = PurePosixPath(entry.name)
            if (path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'package'
                    or not (entry.isfile() or entry.isdir()) or count > 10000):
                raise ValueError('Unsupported linked or unsafe package archive')
            expanded += entry.size
            if expanded > MAX_EXPANDED:
                raise ValueError('Package expansion exceeds the reviewed limit')
    return bytes(content), expanded


class Installer:
    def __init__(self, host):
        self.host = host
        self.store = host.STORE
        self.lock = threading.RLock()
        self.active = {}

    def workspace(self, task_id):
        h = self.host
        if not h.network_policy.offline_only() or not h.AUTH.enabled:
            raise ValueError('Dependency installation requires authenticated local offline mode')
        h.require_execution()
        if h.project_agent.running(task_id) or h.STORE.one("SELECT id FROM rounds WHERE task_id=? AND status='executing'", (task_id,)):
            raise ValueError('Wait for the current coding run before changing dependencies')
        workspace = h.STORE.one("SELECT * FROM workspaces WHERE task_id=? AND status='ready'", (task_id,))
        if not workspace:
            raise ValueError('Create and approve the task worktree first')
        return h.safe_workspace_path(workspace)

    def propose(self, task_id):
        with self.lock:
            if task_id in self.active:
                raise ValueError('Wait for or cancel the current installation')
            root = self.workspace(task_id)
            if os.path.lexists(root / 'node_modules'):
                raise ValueError('Existing node_modules is preserved; replacement is not supported')
            raw = manifests(root)
            packages = package_plan(raw)
            info = root.stat()
            proposal = {'task_id': task_id, 'root': str(root), 'identity': [info.st_dev, info.st_ino],
                        'hashes': {name: project_files.digest(value) for name, value in raw.items()},
                        'packages': packages, 'command': COMMAND, 'network': {
                            'origin': 'https://registry.npmjs.org', 'requests': [p['url'] for p in packages],
                            'redirects': False, 'credentials': False, 'max_download_bytes': MAX_DOWNLOAD},
                        'writes': ['new task-worktree node_modules', 'private per-install staging and cache'],
                        'scripts': 'All lifecycle scripts disabled; native-addon setup may remain incomplete',
                        'max_expanded_bytes': MAX_EXPANDED}
            encoded = json.dumps(proposal, sort_keys=True)
            identifier, now = self.host.uid(), self.host.now()
            self.host.STORE.write('INSERT INTO dependency_jobs VALUES (?,?,?,?,?,?,?,?,?)',
                                  (identifier, task_id, encoded, project_files.digest(encoded.encode()), 'proposed', '', now, now + 600, now))
            return self.get(task_id, identifier)

    def get(self, task_id, identifier=None):
        self.workspace(task_id)
        row = self.host.STORE.one('SELECT * FROM dependency_jobs WHERE task_id=? ' +
                                 ('AND id=?' if identifier else 'ORDER BY created_at DESC,rowid DESC LIMIT 1'),
                                 (task_id, identifier) if identifier else (task_id,))
        if not row:
            return None
        return {**row, 'proposal': json.loads(row['proposal'])}

    def execute(self, task_id, request):
        if set(request) != {'id', 'digest', 'confirm', 'confirm_network'} or request['confirm'] is not True or request['confirm_network'] is not True:
            raise ValueError('Confirm this exact install and its disclosed registry downloads')
        with self.lock:
            row = self.get(task_id, request['id'])
            if not row or row['digest'] != request['digest'] or project_files.digest(json.dumps(row['proposal'], sort_keys=True).encode()) != row['digest']:
                raise ValueError('The reviewed dependency proposal changed')
            if row['status'] != 'proposed' or row['expires_at'] <= self.host.now():
                raise ValueError('Installation approval is expired or already used; review a new proposal')
            if task_id in self.active:
                raise ValueError('One install per task may run at a time')
            self._validate(row['proposal'])
            with self.host.STORE.lock, self.host.STORE.conn:
                changed = self.host.STORE.conn.execute("UPDATE dependency_jobs SET status='running',updated_at=? WHERE id=? AND status='proposed'", (self.host.now(), row['id']))
                if changed.rowcount != 1:
                    raise ValueError('Installation already claimed')
            stopped = threading.Event()
            thread = threading.Thread(target=self._run, args=(row, stopped), daemon=True)
            self.active[task_id] = (stopped, thread)
            thread.start()
        return self.get(task_id, row['id'])

    def _validate(self, proposal):
        root = self.workspace(proposal['task_id'])
        info = root.stat()
        if str(root) != proposal['root'] or [info.st_dev, info.st_ino] != proposal['identity']:
            raise ValueError('Task worktree identity changed')
        if os.path.lexists(root / 'node_modules'):
            raise ValueError('Existing node_modules was preserved')
        raw = manifests(root)
        if {name: project_files.digest(value) for name, value in raw.items()} != proposal['hashes']:
            raise ValueError('Dependency files changed; review a new installation')
        return root, raw

    def cancel(self, task_id):
        with self.lock:
            active = self.active.get(task_id)
            if active:
                active[0].set()
            return bool(active)

    def close(self):
        with self.lock:
            active = list(self.active.values())
            for event, _ in active:
                event.set()
        for _, thread in active:
            thread.join(15)
        return all(not thread.is_alive() for _, thread in active)

    def _command(self, argv, job, stage, cache, stopped):
        launch = local_runner.sandboxed(argv, reads=(job,), writes=(job,), programs=(local_runner.trusted_program('node'),))
        for name in ('user.npmrc', 'global.npmrc'):
            (job / name).touch(exist_ok=True)
        env = {**local_runner.base_env(stage), 'TMPDIR': str(job), 'npm_config_cache': str(cache),
               'npm_config_userconfig': str(job / 'user.npmrc'), 'npm_config_globalconfig': str(job / 'global.npmrc'),
               'npm_config_offline': 'true', 'npm_config_ignore_scripts': 'true', 'NODE_OPTIONS': '--max-old-space-size=512'}
        with (job / 'command.log').open('wb') as output:
            process = subprocess.Popen(launch, cwd=stage, env=env, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=True, preexec_fn=lambda: self.host.child_limits(120, address_space=False))
            deadline = time.monotonic() + 120
            try:
                while process.poll() is None:
                    if stopped() or time.monotonic() >= deadline:
                        raise ValueError('Installation cancelled or command timed out')
                    time.sleep(.05)
                if process.returncode:
                    with (job / 'command.log').open('rb') as log:
                        detail = log.read(2000).decode('utf-8', errors='replace')
                    raise ValueError('Offline npm command failed: ' + self.host.redacted(detail))
            finally:
                self.host.terminate_process_group(process)

    def _run(self, row, cancellation):
        h, proposal = self.host, row['proposal']
        if isinstance(proposal, str):
            proposal = json.loads(proposal)
        status, detail = 'failed', 'Installation ended before completion'
        deadline = time.monotonic() + 300
        def stopped():
            return cancellation.is_set() or h.STOPPING.is_set() or time.monotonic() >= deadline
        def progress(message):
            h.STORE.write('UPDATE dependency_jobs SET output=?,updated_at=? WHERE id=?', (message, h.now(), row['id']))
        try:
            root, raw = self._validate(proposal)
            parent = h.DATA / 'dependency-installs'
            parent.mkdir(mode=0o700, exist_ok=True)
            job = parent / row['id']
            job.mkdir(mode=0o700)
            stage, cache = job / 'stage', job / 'cache'
            stage.mkdir(mode=0o700)
            cache.mkdir(mode=0o700)
            for name, content in raw.items():
                project_files.write_file(stage, name, content)
            compressed = expanded = 0
            for index, package in enumerate(proposal['packages']):
                if stopped():
                    raise ValueError('Installation cancelled')
                progress(f"Downloading and verifying package {index + 1}/{len(proposal['packages'])}")
                data, size = download(package, stopped)
                compressed += len(data)
                expanded += size
                if compressed > MAX_DOWNLOAD or expanded > MAX_EXPANDED:
                    raise ValueError('Total dependency size exceeds the reviewed budget')
                tarball = job / f'package-{index}.tgz'
                tarball.write_bytes(data)
                self._command(['npm', 'cache', 'add', str(tarball), '--offline', '--ignore-scripts', '--no-audit', '--no-fund'], job, stage, cache, stopped)
            progress('Installing verified cached packages offline; lifecycle scripts disabled')
            self._command(COMMAND, job, stage, cache, stopped)
            root, _ = self._validate(proposal)
            if stopped():
                raise ValueError('Installation cancelled before publication')
            # Claim a new destination exclusively; never replace an existing dependency tree.
            with project_files.parent_directory(root, 'node_modules', root_identity=proposal['identity']) as (parent_fd, leaf):
                os.mkdir(leaf, mode=0o700, dir_fd=parent_fd)
                if (stage / 'node_modules').is_dir():
                    os.rename(stage / 'node_modules', leaf, dst_dir_fd=parent_fd)
            status, detail = 'complete', 'Installed locked dependencies; all lifecycle scripts were disabled. Existing source and lockfile preserved.'
        except Exception as error:
            status = 'cancelled' if stopped() else 'failed'
            detail = h.redacted(str(error))[:3000] or 'Installation failed; staging preserved'
        finally:
            try:
                h.STORE.write('UPDATE dependency_jobs SET status=?,output=?,updated_at=? WHERE id=?', (status, detail, h.now(), row['id']))
            finally:
                with self.lock:
                    self.active.pop(row['task_id'], None)
