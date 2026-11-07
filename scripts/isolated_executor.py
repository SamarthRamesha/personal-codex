#!/usr/bin/env python3
"""Trusted container entrypoint. Refuses commands unless required Linux controls are active."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import isolation,secure_files,security


def execute(value,checks):
    if not checks or not all(checks.values()):raise ValueError('Required OS isolation controls are unavailable; no command executed')
    files=isolation.validate(value);root=Path('/workspace')
    if any(root.iterdir()):raise ValueError('Workspace must be an empty bounded tmpfs')
    for name,data in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);secure_files.write_new(path,data)
    started=time.monotonic();output=bytearray();failure='';process=None
    try:
        process=subprocess.Popen(value['argv'],cwd=root,env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/tmp','PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'},stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
        selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
        try:
            while selector.get_map():
                if time.monotonic()-started>value['timeout_seconds']:failure='timeout';break
                for key,_ in selector.select(.1):
                    chunk=os.read(key.fileobj.fileno(),8192)
                    if not chunk:selector.unregister(key.fileobj);break
                    output.extend(chunk)
                    if len(output)>100_000:failure='output budget';break
                if failure:break
        finally:selector.close()
    finally:
        if process is not None:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=3);process.stdout.close()
    changed=secure_files.read_tree(root,max_bytes=isolation.MAX_INPUT,max_files=isolation.MAX_FILES,reject_name=isolation.secret_name)
    return {'version':1,'id':value['id'],'request_sha256':value['request_sha256'],'checks':checks,'exit_code':process.returncode,'failure':failure,
            'output':bytes(output[:100_000]).decode('utf-8',errors='replace'),'elapsed_ms':int((time.monotonic()-started)*1000),
            'changed_files':{name:isolation.sha(data) for name,data in changed.items() if files.get(name)!=data},'test_result_is_untrusted':True}


def main():
    checks={}
    try:
        checks=isolation.runtime_checks()
        if sys.argv[1:]==['--probe']:result={'checks':checks,'verified':bool(checks) and all(checks.values()),'command_executed':False}
        else:
            if not all(checks.values()):raise ValueError('OS isolation checks failed; execution disabled')
            raw=sys.stdin.buffer.read(isolation.MAX_REQUEST+1)
            if len(raw)>isolation.MAX_REQUEST:raise ValueError('Request too large')
            value=json.loads(raw,object_pairs_hook=security.unique_json_object);result=execute(value,checks)
    except (ValueError,OSError,subprocess.SubprocessError):
        print(json.dumps({'verified':False,'checks':checks,'command_executed':False,'error':'Isolation, snapshot or execution contract failed; no trusted completion'}));return 2
    print(json.dumps(result));return 0 if result.get('verified',result.get('exit_code')==0 and not result.get('failure')) else 2

if __name__=='__main__':raise SystemExit(main())
