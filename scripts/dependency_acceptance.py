#!/usr/bin/env python3
"""Explicit opt-in registry install acceptance in a new disposable profile."""
import argparse
import http.client
import json
import os
from pathlib import Path
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', action='store_true', help='authorize public is-number@7.0.0 metadata and tarball download')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not args.registry:
        parser.error('Explicit --registry confirmation required; no network access attempted')
    out = args.output.resolve()
    out.mkdir(mode=0o700)
    os.environ.update(PERSONAL_CODEX_DATA=str(out / 'state'), PERSONAL_CODEX_INFERENCE_POLICY='offline',
                      PERSONAL_CODEX_PROJECT_ROOTS=str(out / 'state/projects'))
    from app import dependencies, security, server
    server.AUTH = security.OwnerAuth(secrets.token_urlsafe(32))
    server.STORE = server.Store()
    task, project = server.uid(), server.uid()
    source = server.DATA / 'projects' / 'fixture'
    source.mkdir(parents=True)
    root = server.DATA / 'workspaces' / task
    root.mkdir(parents=True)
    server.STORE.write('INSERT INTO projects VALUES (?,?,?,?)', (project, 'Synthetic dependency acceptance', str(source), server.now()))
    server.STORE.write('INSERT INTO workspaces VALUES (?,?,?,?,?,?)', (task, project, str(root), 'synthetic', 'ready', server.now()))
    client = http.client.HTTPSConnection('registry.npmjs.org', timeout=15)
    try:
        client.request('GET', '/is-number/7.0.0')
        response = client.getresponse()
        if response.status != 200: raise ValueError('Exact public package metadata unavailable')
        data = response.read(100001)
        if len(data) > 100000: raise ValueError('Package metadata exceeds acceptance budget')
        package = json.loads(data)
    finally:
        client.close()
    manifest = {'name':'acceptance', 'version':'1.0.0', 'dependencies':{'is-number':'7.0.0'}}
    lock = {'name':'acceptance', 'version':'1.0.0', 'lockfileVersion':3, 'packages':{
        '':manifest, 'node_modules/is-number':{'version':'7.0.0', 'resolved':package['dist']['tarball'], 'integrity':package['dist']['integrity']}}}
    (root / 'package.json').write_text(json.dumps(manifest))
    (root / 'package-lock.json').write_text(json.dumps(lock))
    service = dependencies.Installer(server)
    try:
        review = service.propose(task)
        service.execute(task, {'id':review['id'], 'digest':review['digest'], 'confirm':True, 'confirm_network':True})
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            result = service.get(task)
            if result['status'] != 'running': break
            time.sleep(.1)
        if result['status'] != 'complete': raise ValueError(result['output'])
        if not (root / 'node_modules/is-number/index.js').is_file(): raise ValueError('Package was not installed')
        receipt = {'ok':True, 'registry':'https://registry.npmjs.org', 'package':'is-number@7.0.0',
                   'proposal_digest':review['digest'], 'status':result['status'], 'lifecycle_scripts':False,
                   'workspace':str(root), 'jarvis_accessed':False}
        (out / 'evidence.json').write_text(json.dumps(receipt, indent=2))
        print(json.dumps(receipt, indent=2))
    finally:
        service.close()
        server.STORE.close()


if __name__ == '__main__': main()
