#!/usr/bin/env python3
"""Offline encrypted checkpoint/restore. Infrastructure/service changes need separate approval."""
import argparse
import json
from pathlib import Path
import sys
import sqlite3
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import recovery


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='operation',required=True)
    create=sub.add_parser('checkpoint');create.add_argument('--data',type=Path,required=True);create.add_argument('--output',type=Path,required=True);create.add_argument('--key-file',type=Path,required=True);create.add_argument('--release-zip',type=Path,required=True);create.add_argument('--review-env',type=Path)
    restore=sub.add_parser('restore');restore.add_argument('--bundle',type=Path,required=True);restore.add_argument('--new-root',type=Path,required=True);restore.add_argument('--key-file',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.operation=='checkpoint':
            from scripts.deployment_preflight import read_settings
            config=read_settings(args.review_env) if args.review_env else None
            result=recovery.checkpoint(args.data,args.output,args.key_file,args.release_zip,config)
        else:result=recovery.restore(args.bundle,args.new_root,args.key_file)
    except (ValueError,OSError,sqlite3.Error):parser.exit(2,'Recovery failed safely; inspect scope, private key metadata, limits and quiescent backend. No existing file replaced.\n')
    print(json.dumps(result))

if __name__=='__main__':main()
