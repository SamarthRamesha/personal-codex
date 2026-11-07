#!/usr/bin/env python3
"""Read-only authenticated HTTPS acceptance. Never starts inference or changes a task/service."""
import argparse
import http.client
import json
from pathlib import Path
import ssl
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import mac_worker,providers,security,secure_files


class CheckError(ValueError):pass


class Client:
    PATHS={'/api/health','/api/connection','/api/ready','/api/inference/status','/api/diagnostics','/api/projects','/api/worker/poll'}
    def __init__(self,url,allow_loopback=False):
        self.parsed,self.host,self.port=mac_worker.backend_url(url)
        if not allow_loopback and security.is_loopback(self.host):raise CheckError('Production acceptance requires the exact private HTTPS origin')
        self.production=not security.is_loopback(self.host)
    def get(self,path,token=None):
        if path not in self.PATHS:raise CheckError('Read-only acceptance path required')
        connection=http.client.HTTPSConnection(self.host,self.port,timeout=5,context=ssl.create_default_context()) if self.parsed.scheme=='https' else http.client.HTTPConnection(self.host,self.port,timeout=5)
        response=None;guard=providers._StreamGuard(connection,lambda:False,5)
        try:
            headers={'Connection':'close'}
            if token:headers['Authorization']='Bearer '+token
            connection.request('GET',path,headers=headers);guard.socket=connection.sock
            if guard.reason:raise CheckError('Acceptance deadline exceeded')
            response=connection.getresponse();raw=response.read(1_000_001)
            if guard.reason or len(raw)>1_000_000:raise CheckError('Acceptance response deadline/size limit exceeded')
            value=json.loads(raw,object_pairs_hook=security.unique_json_object)
            if not isinstance(value,dict):raise CheckError('Acceptance response must be an object')
            return response.status,value
        except (OSError,http.client.HTTPException,ValueError):raise CheckError('HTTPS, authentication, framing or response verification failed') from None
        finally:
            guard.close()
            if response is not None:response.close()
            connection.close()


def assess(client,owner,worker,model):
    checks={}
    status,health=client.get('/api/health');checks['liveness']=status==200 and health.get('ok') is True
    checks['unauthenticated_owner_rejected']=client.get('/api/connection')[0]==401
    status,connection=client.get('/api/connection',owner)
    checks['owner_authenticated']=status==200 and connection.get('authenticated') is True and connection.get('api_version')==1
    checks['private_https']=client.production and connection.get('secure_transport') is True and connection.get('public_origin')==client.parsed.geturl().rstrip('/')
    checks['coding_disabled']=connection.get('execution_mode')=='disabled' and connection.get('capabilities',{}).get('repository_execution') is False
    status,ready=client.get('/api/ready',owner);checks['readiness']=status==200 and ready.get('ready') is True
    status,inference=client.get('/api/inference/status',owner)
    checks['installed_worker_model']=status==200 and inference.get('worker',{}).get('online') is True and model in inference.get('worker',{}).get('models',[])
    checks['worker_has_no_owner_authority']=client.get('/api/projects',worker)[0]==403
    checks['owner_has_no_worker_authority']=client.get('/api/worker/poll',owner)[0]==401
    status,diagnostics=client.get('/api/diagnostics',owner)
    policy=diagnostics.get('network_policy',{})
    checks['worker_only_inference']=policy.get('inference_policy')=='worker-only'
    checks['backend_outbound_connections_denied']=policy.get('outbound_connections_denied') is True
    checks['storage_admission_enabled']=status==200 and diagnostics.get('storage_enforcement',{}).get('write_admission') is True
    checks['storage_inventory_complete']=diagnostics.get('storage',{}).get('measurement_complete') is True
    checks['no_declared_telemetry_or_cloud_fallback']=diagnostics.get('telemetry') is False and diagnostics.get('cloud_fallback') is False
    return {'checks':checks,'http_acceptance_passed':all(checks.values()),'remote_acceptance_complete':False,'mutations':False,
            'remaining':['actual private-network ACL tests from allowed and denied devices','listener/runtime/resource/disk inspection','real remote chat/stream/stop/retry/restart','encrypted restore drill on target','coding OS isolation acceptance if ever enabled']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--backend',required=True);p.add_argument('--owner-token-file',required=True);p.add_argument('--worker-token-file',required=True);p.add_argument('--model',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        result=assess(Client(a.backend),mac_worker.read_token(a.owner_token_file),mac_worker.read_token(a.worker_token_file),a.model)
        secure_files.write_new(a.output,json.dumps(result,indent=2).encode())
    except (ValueError,OSError):p.exit(2,'Read-only acceptance failed; inspect verified HTTPS, private credential metadata and service readiness. No mutation attempted.\n')
    print(json.dumps({'http_acceptance_passed':result['http_acceptance_passed'],'remote_acceptance_complete':False,'mutations':False}));return 0 if result['http_acceptance_passed'] else 2

if __name__=='__main__':raise SystemExit(main())
