#!/usr/bin/env python3
"""Operator-only prototype. Requires explicit approval flag; never used by API/agent tools."""
import argparse
import json
import os
from pathlib import Path
import platform
import selectors
import signal
import subprocess
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import isolation,secure_files,security


class ExecutionError(ValueError):pass


def capture(argv,payload=b'',timeout=10):
    # Discard inherited Docker contexts, proxy variables, credentials and registry config.
    process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                             env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','DOCKER_CONFIG':'/nonexistent'},start_new_session=True)
    def feed():
        try:process.stdin.write(payload)
        except (OSError,ValueError):pass
        finally:
            try:process.stdin.close()
            except OSError:pass
    writer=threading.Thread(target=feed,daemon=True);writer.start()
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ);output=bytearray();started=time.monotonic()
    try:
        while selector.get_map() or process.poll() is None:
            if time.monotonic()-started>timeout:raise ExecutionError('Supervisor total deadline exceeded; completion unknown')
            for key,_ in selector.select(.05):
                block=os.read(key.fileobj.fileno(),8192)
                if not block:selector.unregister(key.fileobj);continue
                output.extend(block)
                if len(output)>isolation.MAX_OUTPUT:raise ExecutionError('Supervisor output budget exceeded; completion rejected')
        return process.wait(timeout=1),bytes(output)
    finally:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=2);writer.join(1);selector.close();process.stdout.close()


def run_reviewed(request_file,expected_sha,image,uid,gid,daemon_socket,docker='/usr/bin/docker'):
    if platform.system()!='Linux':raise ExecutionError('Actual Linux Docker runtime required; no execution attempted')
    value=isolation.read_request(request_file)
    if value['request_sha256']!=expected_sha:raise ExecutionError('Operator reviewed digest does not match')
    parent=Path(request_file).absolute().parent;info=parent.stat()
    if info.st_uid!=os.getuid() or info.st_mode&0o077:raise ExecutionError('Operator job directory must be private')
    argv=isolation.docker_argv(value,image,uid,gid,daemon_socket,docker)
    # An immutable claim precedes every possible Docker action. Ambiguous failures never auto-replay.
    secure_files.write_new(parent/'started.json',json.dumps({'id':value['id'],'request_sha256':expected_sha,'created_at':int(time.time())}).encode())
    # Reject implicit image volumes; only this explicitly reviewed cached image is inspected.
    code,raw=capture([docker,'--host','unix://'+daemon_socket,'image','inspect','--format','{{json .Config.Volumes}}',image])
    if code!=0 or json.loads(raw) not in (None,{}):raise ExecutionError('Reviewed executor image unavailable or declares implicit volumes')
    probe=list(argv);probe[probe.index('--name')+1]+='-probe';probe+=['--probe']
    try:
        code,raw=capture(probe,timeout=15);proof=json.loads(raw,object_pairs_hook=security.unique_json_object)
        if code!=0 or proof.get('verified') is not True or not proof.get('checks') or not all(proof['checks'].values()):raise ExecutionError('Trusted runtime probe failed; no repository command executed')
        secure_files.write_new(parent/'isolation-proof.json',raw)
        code,raw=capture(argv,isolation.canonical(value),value['timeout_seconds']+15)
        result=json.loads(raw,object_pairs_hook=security.unique_json_object)
        if (code!=0 or result.get('id')!=value['id'] or result.get('request_sha256')!=expected_sha
                or result.get('exit_code')!=0 or result.get('failure') or result.get('test_result_is_untrusted') is not True):
            raise ExecutionError('Isolated tests failed or completion is ambiguous; no patch/approval granted')
        secure_files.write_new(parent/'result.json',raw)
        return {'completed':True,'job_id':value['id'],'runtime_probe_passed':True,'backend_execution_enabled':False,'patch_applied':False,'result_is_untrusted':True}
    finally:
        # Only our unique, approved ephemeral job names; no prune, service or volume operations.
        for name in (argv[argv.index('--name')+1],probe[probe.index('--name')+1]):
            try:subprocess.run([docker,'--host','unix://'+daemon_socket,'kill','--signal','KILL',name],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3,env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','DOCKER_CONFIG':'/nonexistent'})
            except (OSError,subprocess.TimeoutExpired):pass


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--image-id',required=True);p.add_argument('--uid',type=int,required=True);p.add_argument('--gid',type=int,required=True);p.add_argument('--daemon-socket',required=True);p.add_argument('--docker',default='/usr/bin/docker');p.add_argument('--execute-approved',action='store_true');a=p.parse_args()
    if not a.execute_approved:p.error('This creates ephemeral Docker workloads: obtain explicit approval, then pass --execute-approved')
    try:result=run_reviewed(a.request,a.expected_sha256,a.image_id,a.uid,a.gid,a.daemon_socket,a.docker)
    except (ValueError,OSError,subprocess.SubprocessError):p.exit(2,'Isolation failed closed or is unavailable. Inspect private receipts; no existing task replayed and backend execution remains disabled.\n')
    print(json.dumps(result))

if __name__=='__main__':main()
