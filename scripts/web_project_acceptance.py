#!/usr/bin/env python3
"""Real local-model web implementation, reviewed install, preview and independent HTTP checks.
Uses a supplied manifest/test baseline in a wholly new disposable Git repository.
"""
import argparse
from http.client import HTTPConnection, HTTPSConnection
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',required=True)
    parser.add_argument('--registry',action='store_true',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',default='qwen3.5:9b',choices=['qwen3.5:9b','qwen2.5-coder:14b'])
    parser.add_argument('--hold',action='store_true',help='keep only this synthetic backend/preview alive for UI inspection, at most 15 minutes')
    parser.add_argument('--app',type=Path,help='launch this isolated native candidate with this fixture profile')
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(mode=0o700)
    token=secrets.token_urlsafe(32)
    os.environ.update(PERSONAL_CODEX_DATA=str(out/'state'),PERSONAL_CODEX_PROJECT_ROOTS=str(out/'state/projects'),
                      PERSONAL_CODEX_INFERENCE_POLICY='offline',PERSONAL_CODEX_OFFLINE_MODEL=args.model,
                      PERSONAL_CODEX_INSTALLED_OFFLINE_MODELS=args.model,PERSONAL_CODEX_NATIVE_GRANT=secrets.token_urlsafe(32))
    from app import providers,security,server
    if args.model not in providers.discover_models(server.network_policy.OLLAMA_ENDPOINT):raise ValueError('Selected local model is unavailable')
    server.AUTH=security.OwnerAuth(token);server.STORE=server.Store();server.seed_offline_providers()
    http=server.runtime.ControlServer(('127.0.0.1',0),server.App)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    def api(path,body=None,expected=200,native=False):
        client=HTTPConnection('127.0.0.1',http.server_port,timeout=60)
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
        if native:headers['X-Personal-Codex-Native']=os.environ['PERSONAL_CODEX_NATIVE_GRANT']
        try:
            client.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
            response=client.getresponse();value=json.loads(response.read())
            if response.status!=expected:raise ValueError(f'{response.status}: {value}')
            return value
        finally:client.close()
    started=time.monotonic();gui=None
    try:
        parent=server.DATA/'projects';parent.mkdir(parents=True,exist_ok=True)
        info=parent.stat()
        project=api('/api/native/projects',{'parent':str(parent),'name':'Web Calculator','device':info.st_dev,'inode':info.st_ino},201,True)
        source=Path(project['path'])
        registry=HTTPSConnection('registry.npmjs.org',timeout=15)
        try:
            registry.request('GET','/is-number/7.0.0');response=registry.getresponse()
            if response.status!=200:raise ValueError('Public fixture metadata unavailable')
            data=response.read(100001)
            if len(data)>100000:raise ValueError('Fixture metadata too large')
            package=json.loads(data)
        finally:registry.close()
        manifest={'name':'web-calculator','version':'1.0.0','scripts':{'test':'node --test','dev':'node server.js'},'dependencies':{'is-number':'7.0.0'}}
        lock={'name':'web-calculator','version':'1.0.0','lockfileVersion':3,'packages':{'':manifest,
              'node_modules/is-number':{'version':'7.0.0','resolved':package['dist']['tarball'],'integrity':package['dist']['integrity']}}}
        test="const test=require('node:test');const assert=require('node:assert/strict');const {add}=require('../calc.js');test('addition',()=>assert.equal(add(2,3),5));test('negative values',()=>assert.equal(add(-2,3),1));test('reject invalid values',()=>assert.throws(()=>add('x',3)));"
        (source/'tests').mkdir();(source/'tests/acceptance.test.js').write_text(test)
        (source/'package.json').write_text(json.dumps(manifest));(source/'package-lock.json').write_text(json.dumps(lock))
        (source/'.gitignore').write_text('node_modules/\n')
        for argv in (['add','--','package.json','package-lock.json','tests/acceptance.test.js','.gitignore'],
                     ['-c','user.name=Synthetic acceptance','-c','user.email=fixture@example.invalid','-c','core.hooksPath=/dev/null','commit','-m','Independent web acceptance baseline']):
            subprocess.run(['git','-C',str(source),*argv],check=True,capture_output=True)
        prompt=("Implement this Node CommonJS web calculator. Existing package.json, package-lock.json and tests/acceptance.test.js are supplied trusted baseline: do not change them. "
                "Create calc.js exporting add(a,b), accepting finite numbers only and throwing on invalid inputs. Create server.js serving public/index.html at / and JSON {sum:5} at /api/add?a=2&b=3 using add; invalid inputs return HTTP400. "
                "Create public/index.html titled Web Calculator with two number inputs, an Add button and a result element; its script fetches /api/add and displays the sum. "
                "Use built-in Node http/fs/path/url modules, and require is-number only inside the HTTP request handler if used: dependencies install AFTER code tests. "
                "server.js must listen on process.env.PORT and process.env.HOST. The declared dev script is node server.js. Run the independent existing tests with npm test or node --test. "
                "Use no downloads, new dependencies, external services or extra test files. Deliver the complete requested source and README.")
        task=api('/api/full-tasks',{'project_id':project['id'],'prompt':prompt,'attachments':[],
                 'provider_id':'offline-ollama-'+args.model,'rounds':8,'seconds':540,'confirm':True},202)['task_id']
        deadline=time.monotonic()+550
        while time.monotonic()<deadline:
            run=api(f'/api/tasks/{task}/autonomous')
            if run['status']!='running':break
            time.sleep(.5)
        (out/'coding-evidence.json').write_text(json.dumps(run,indent=2))
        if run['status']!='complete':raise ValueError('Real-model coding incomplete: '+run['summary'])
        if (source/'tests/acceptance.test.js').read_text()!=test:raise ValueError('Independent tests changed')
        install=api(f'/api/tasks/{task}/dependencies/propose',{},201)
        api(f'/api/tasks/{task}/dependencies/execute',{'id':install['id'],'digest':install['digest'],'confirm':True,'confirm_network':True},202)
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            result=api(f'/api/tasks/{task}/dependencies')
            if result['status']!='running':break
            time.sleep(.2)
        if result['status']!='complete':raise ValueError('Dependency installation failed: '+result['output'])
        import socket
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        preview=api(f'/api/tasks/{task}/preview/propose',{'script':'dev','port':port},201)
        api(f'/api/tasks/{task}/preview/execute',{'id':preview['id'],'digest':preview['digest'],'confirm':True},202)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            current=api(f'/api/tasks/{task}/preview')
            if current['status']!='starting':break
            time.sleep(.1)
        if current['status']!='running':raise ValueError('Preview failed: '+current['output']+' '+current['logs'])
        for path,expected in (('/',None),('/api/add?a=2&b=3',{'sum':5}),('/api/add?a=-2&b=3',{'sum':1})):
            client=HTTPConnection('127.0.0.1',port,timeout=5)
            try:
                client.request('GET',path);response=client.getresponse();content=response.read(100000)
                if response.status!=200:raise ValueError('Independent HTTP status failed')
                if expected is not None and json.loads(content)!=expected:raise ValueError('Independent API result failed')
                if expected is None and b'Web Calculator' not in content:raise ValueError('Frontend title missing')
            finally:client.close()
        receipt={'ok':True,'live_model':args.model,'seconds':round(time.monotonic()-started,2),'task_id':task,
                 'backend':f'http://127.0.0.1:{http.server_port}','preview':current['proposal']['url'],
                 'checks':['real-model implementation from supplied manifest/tests','independent tests unchanged',
                           'reviewed registry installation','owned loopback preview','independent frontend/API responses'],
                 'jarvis_accessed':False}
        (out/'evidence.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2),flush=True)
        if args.app:
            private_token=out/'owner.token'
            descriptor=os.open(private_token,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'w') as stream:stream.write(token)
            env={key:os.environ[key] for key in ('HOME','PATH','USER','LOGNAME','TMPDIR','LANG') if key in os.environ}
            gui=subprocess.Popen([str(args.app/'Contents/MacOS/personal-codex')],env={**env,
                 'PERSONAL_CODEX_OFFLINE_TOKEN_FILE':str(private_token),'PERSONAL_CODEX_OFFLINE_PORT':str(http.server_port),
                 'PERSONAL_CODEX_NATIVE_GRANT':os.environ['PERSONAL_CODEX_NATIVE_GRANT']})
        if args.hold:
            deadline=time.monotonic()+900
            while time.monotonic()<deadline and not (out/'STOP').exists():time.sleep(.2)
        api(f'/api/tasks/{task}/preview/stop',{})
    finally:
        if gui and gui.poll() is None:gui.terminate();gui.wait(timeout=10)
        server.project_agent.stop_all()
        if server._DEPENDENCIES:server._DEPENDENCIES.close()
        if server._PREVIEWS:server._PREVIEWS.close()
        http.shutdown();http.server_close();thread.join();server.STORE.close()


if __name__=='__main__':main()
