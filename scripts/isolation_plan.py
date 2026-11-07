#!/usr/bin/env python3
"""Create an isolated request and fixed Docker argv for review; never invokes Docker."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import isolation,secure_files


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--image-id',required=True);p.add_argument('--uid',type=int,required=True);p.add_argument('--gid',type=int,required=True);p.add_argument('--daemon-socket',required=True);p.add_argument('--timeout',type=int,default=30);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    try:
        command=a.command[1:] if a.command[:1]==['--'] else a.command
        value=isolation.request(a.source,command,a.timeout);argv=isolation.docker_argv(value,a.image_id,a.uid,a.gid,a.daemon_socket)
        secure_files.no_symlink_parents(a.output.parent)
        a.output.mkdir(mode=0o700)  # explicit new local staging path; never a server installation action
        secure_files.write_new(a.output/'request.json',isolation.canonical(value))
        secure_files.write_new(a.output/'plan.json',json.dumps({'argv':argv,'request_sha256':value['request_sha256'],'runtime_verified':False,'backend_execution_enabled':False},indent=2).encode())
    except (ValueError,OSError):p.exit(2,'Cannot prepare isolated request; inspect scope, source secrets/links/budgets and review values.\n')
    print(json.dumps({'id':value['id'],'request_sha256':value['request_sha256'],'runtime_verified':False,'docker_invoked':False}))

if __name__=='__main__':main()
