#!/usr/bin/env python3
"""Deterministic minimal API build context from trusted committed Personal Codex source.

Reads Git objects only, never untracked files/diagnostics/data. No network, Docker, image build,
installation or publication. Intended for this trusted release repo, never agent repositories.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile


def git(repository,*arguments):
    environment={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null'}
    result=subprocess.run(['git','--no-pager','-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null',*arguments],cwd=repository,env=environment,capture_output=True,check=True)
    return result.stdout


def create(repository,revision='HEAD'):
    commit=git(repository,'rev-parse','--verify',revision+'^{commit}').decode().strip()
    if not re.fullmatch(r'[a-f0-9]{40}',commit):raise ValueError('Reviewed SHA-1 source commit required')
    names=git(repository,'ls-tree','-r','--name-only','-z',commit).decode().split('\0')
    selected={name:name for name in names if len(Path(name).parts)==2 and name.startswith('app/') and name.endswith('.py')}
    required={'deploy/Dockerfile':'Dockerfile','web/index.html':'web/index.html','web/app.js':'web/app.js','web/style.css':'web/style.css','scripts/restore_database.py':'scripts/restore_database.py'}
    if not {'app/server.py','app/security.py','app/runtime.py'}.issubset(selected):raise ValueError('Not the expected trusted Personal Codex source tree')
    if not set(required).issubset(names):raise ValueError('Required build input missing from commit')
    selected.update(required);files={target:git(repository,'show',commit+':'+source) for source,target in selected.items()}
    if sum(map(len,files.values()))>2*1024*1024:raise ValueError('API source context unexpectedly exceeds 2 MiB')
    lock=json.loads(git(repository,'show',commit+':deploy/base-image.lock.json'))
    if not re.fullmatch(r'docker.io/library/python@sha256:[a-f0-9]{64}',lock['base_image']):raise ValueError('Reviewed official base digest required')
    raw=io.BytesIO()
    with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as compressed:
        with tarfile.open(fileobj=compressed,mode='w',format=tarfile.USTAR_FORMAT) as archive:
            for name,value in sorted(files.items()):
                member=tarfile.TarInfo(name);member.size=len(value);member.mode=0o644;member.mtime=0;member.uid=member.gid=0;member.uname=member.gname=''
                archive.addfile(member,io.BytesIO(value))
    payload=raw.getvalue()
    return payload,{'source_commit':commit,'context_sha256':hashlib.sha256(payload).hexdigest(),'context_bytes':len(payload),'base_image':lock['base_image'],
                    'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(files.items())},
                    'docker_invoked':False,'image_built':False,'private_runtime_data_included':False,'reproducible_context_only':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repository',type=Path,default=Path.cwd());parser.add_argument('--commit',default='HEAD');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--manifest',type=Path,required=True);args=parser.parse_args()
    try:
        if args.output.exists() or args.manifest.exists():raise FileExistsError('Output already exists')
        payload,manifest=create(args.repository,args.commit)
        for path,value in [(args.output,payload),(args.manifest,(json.dumps(manifest,indent=2)+'\n').encode())]:
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream:stream.write(value)
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):parser.exit(2,'Cannot prepare committed build inputs; no existing artifact replaced or Docker action attempted.\n')
    print(json.dumps({key:manifest[key] for key in ('source_commit','context_sha256','context_bytes','image_built')}))

if __name__=='__main__':main()
