#!/usr/bin/env python3
"""Opt-in local-model coding proof using only a disposable, synthetic Git fixture.

Uses the real HTTP API, owner authentication, worktree, provider, digest approval,
patch and test runner. Never registers private code. Artifacts remain under --output.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,help='exact installed local Ollama model')
    parser.add_argument('--output',required=True,help='new directory for isolated synthetic repo, database and evidence')
    args=parser.parse_args()
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False)
    os.environ['PERSONAL_CODEX_DATA']=str(output/'control-data')
    from http.server import ThreadingHTTPServer
    from app import server, security
    token=secrets.token_urlsafe(48);server.AUTH=security.OwnerAuth(token)
    server.STREAM_PROVIDER=True
    repo=output/'fixture';repo.mkdir()
    (repo/'calculator.py').write_text('def add(a, b):\n    return a - b\n')
    (repo/'test_calculator.py').write_text('import unittest\nfrom calculator import add\n\nclass AddTests(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n        self.assertEqual(add(-2, 3), 1)\n')
    for command in (['git','init'],['git','config','user.email','fixture@example.invalid'],['git','config','user.name','Synthetic Fixture'],['git','add','.'],['git','commit','-m','synthetic broken addition fixture']):
        subprocess.run(command,cwd=repo,check=True,capture_output=True)
    http=ThreadingHTTPServer(('127.0.0.1',0),server.App)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{http.server_port}'
    report={'model':args.model,'inference':'local Ollama on Mac; not ZimaOS','checks':[], 'desktop_ui_exercised':False}
    started=time.monotonic()
    def call(path,body=None,method=None):
        raw=json.dumps(body).encode() if body is not None else None
        request=urllib.request.Request(base+path,data=raw,method=method or ('POST' if raw is not None else 'GET'),headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
        try:
            with urllib.request.urlopen(request,timeout=180) as response:return json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'{path}: HTTP {error.code}: {error.read().decode()[:500]}') from None
    def check(name,value,detail=''):
        report['checks'].append({'check':name,'ok':bool(value),'detail':detail})
        if not value:raise RuntimeError(name+': '+detail)
    def approve(aid):call('/api/approvals/'+aid,{'status':'approved'},'PATCH')
    try:
        call('/api/connection');check('authenticated HTTP connection',True)
        provider=call('/api/providers',{'kind':'ollama','endpoint':'http://127.0.0.1:11434','model':args.model})
        models=call('/api/providers/'+provider['id']+'/models')['models'];check('model installed',args.model in models)
        project=call('/api/projects',{'path':str(repo),'name':'Disposable addition fixture'})
        conversation=call('/api/conversations',{'provider_id':provider['id'],'project_id':project['id'],'model':args.model})
        turn=call('/api/conversations/'+conversation['id']+'/messages',{'content':'Reply with one sentence confirming you can help fix an addition function.'})
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            chat=call('/api/conversations/'+conversation['id'])
            if not chat['active_messages']:break
            time.sleep(.25)
        answer=chat['conversation']['messages'][-1]
        check('real chat response persisted',answer['status']=='complete',answer.get('error') or '')
        prompt=('Fix calculator.py: add(a, b) currently returns a - b and must return a + b. '
                'Change only calculator.py using apply_patch with old_text "return a - b" and new_text "return a + b", '
                'then run_tests with command "python3 -m unittest discover -v". Do not change tests. '
                'After the approved patch and tests have executed successfully, report status complete with operations [].')
        task=call('/api/conversations/'+conversation['id']+'/task',{'prompt':prompt});tid=task['id']
        workspace_request=call(f'/api/tasks/{tid}/workspace-request',{});approve(workspace_request['id'])
        workspace=call(f'/api/tasks/{tid}/workspace',{});check('approved isolated worktree',Path(workspace['path'])!=repo)
        request=call(f'/api/tasks/{tid}/agent/round/request',{'provider_id':provider['id']});approve(request['approval_id'])
        plan_started=time.monotonic()
        proposal=call(f'/api/tasks/{tid}/agent/round/plan',{'provider_id':provider['id']})
        report['plan_latency_ms']=int((time.monotonic()-plan_started)*1000)
        pending=server.STORE.one("SELECT * FROM proposals WHERE task_id=? AND status='pending'",(tid,))
        check('real model produced proposal',pending is not None)
        operations=json.loads(pending['operations'])
        # Review every synthetic-fixture operation before any approval. Never accept arbitrary model commands.
        permitted=all((op['tool']=='list_files' and op['path']=='.') or (op['tool']=='read_file' and op['path']=='calculator.py') or (op['tool']=='apply_patch' and op['path']=='calculator.py' and op['old_text'].strip()=='return a - b' and op['new_text'].strip()=='return a + b') or (op['tool']=='run_tests' and op['command']=='python3 -m unittest discover -v') for op in operations)
        check('fixture-only operation review',permitted,json.dumps(operations)[:1500])
        review=call(f'/api/tasks/{tid}/agent/diff');check('digest-bound diff is current',review['digest_valid'] and not review['stale'])
        report['diff']=review
        approval=server.STORE.one("SELECT * FROM approvals WHERE kind='modify' AND project_id=? AND status='pending'",(project['id'],))
        check('proposal requires separate approval',approval is not None)
        approve(approval['id']);call(f'/api/tasks/{tid}/agent/round/execute',{})
        rounds=call(f'/api/tasks/{tid}/agent/rounds')
        check('real patch and approved tests passed',rounds['rounds'][-1]['status']=='passed',json.dumps(rounds['rounds'][-1].get('test_result')))
        check('source repository preserved',(repo/'calculator.py').read_text()=='def add(a, b):\n    return a - b\n')
        check('worktree addition fixed','return a + b' in (Path(workspace['path'])/'calculator.py').read_text())
        report['task_id']=tid;report['conversation_id']=conversation['id'];report['rounds']=rounds
        # Genuine second local-model invocation asks for completion based on persisted test evidence.
        call(f'/api/tasks/{tid}/agent/round/request',{'provider_id':provider['id'],'prompt':'Tests passed and the requested addition fix is verified. Return status complete, summary describing verified evidence, and operations [].'})
        approval=server.STORE.one("SELECT * FROM approvals WHERE project_id=? AND status='pending' ORDER BY rowid DESC LIMIT 1",(project['id'],));approve(approval['id'])
        call(f'/api/tasks/{tid}/agent/round/plan',{'provider_id':provider['id']})
        final=call(f'/api/tasks/{tid}/agent/report');check('evidence-checked task completion',final['status']=='completed',str(final.get('status')))
        report['final_report']=final
        server.STORE.conn.close();server.STORE=server.Store()
        check('conversation and completion survive restart',call('/api/conversations/'+conversation['id'])['conversation']['messages'][-1]['status']=='complete' and call(f'/api/tasks/{tid}/agent/report')['status']=='completed')
        report['ok']=True
    except Exception as error:
        report['ok']=False;report['error']=str(error)[:2000]
    finally:
        report['elapsed_ms']=int((time.monotonic()-started)*1000)
        http.shutdown();http.server_close();thread.join();server.STORE.conn.close()
        (output/'evidence.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({key:report[key] for key in ('model','ok','checks','elapsed_ms')},indent=2))
        if report.get('error'):print(report['error'])
    return 0 if report['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
