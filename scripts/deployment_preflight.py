#!/usr/bin/env python3
"""Read-only review gate. No mkdir, chmod, Docker access, downloads or service changes."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.security import public_origin,OwnerAuth

KEYS={'PC_ROOT','PC_UID','PC_GID','PC_IMAGE','PC_ORIGIN'}
GB=1_000_000_000


def read_settings(path):
    values={}
    for line in Path(path).read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        key,sep,value=line.partition('=')
        if not sep or key not in KEYS or key in values:raise ValueError('Unknown, repeated or invalid setting')
        if any(ch.isspace() for ch in value) or any(ch in value for ch in "'$`\\\""):
            raise ValueError('Settings must be literal unquoted values without shell expansion')
        values[key]=value
    if set(values)!=KEYS:raise ValueError('All five reviewed settings are required')
    return values


def validate_settings(values,parent=Path('/DATA/AppData')):
    root=Path(values['PC_ROOT'])
    if root!=parent/'PersonalCodex' or not root.is_absolute():raise ValueError('Only the dedicated reviewed PersonalCodex path is supported')
    for key in ('PC_UID','PC_GID'):
        if not re.fullmatch(r'[1-9][0-9]{0,8}',values[key]):raise ValueError('Reviewed non-root numeric UID and GID are required')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',values['PC_IMAGE']):raise ValueError('Use a reviewed locally available image ID, not a mutable tag')
    if public_origin(values['PC_ORIGIN'])!=values['PC_ORIGIN'] or '.example.' in values['PC_ORIGIN']:
        raise ValueError('An exact reviewed private HTTPS origin is required')
    return root,int(values['PC_UID']),int(values['PC_GID'])


def no_symlink(path):
    for item in [path,*path.parents]:
        if item.is_symlink():raise ValueError('Deployment path contains a symlink')


def inspect_layout(root,uid,gid):
    # Inspect only these explicitly named paths. No shared-directory listing or data scan.
    for path in (root,root/'data',root/'data'/'projects',root/'secrets'):
        no_symlink(path)
        info=path.stat()
        if not stat.S_ISDIR(info.st_mode) or (info.st_uid,info.st_gid)!=(uid,gid) or stat.S_IMODE(info.st_mode)!=0o700:
            raise ValueError('Dedicated directories must already be private 0700 and owned by the approved UID/GID')
    tokens=[]
    for name in ('owner-token','worker-token'):
        path=root/'secrets'/name;no_symlink(path)
        fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(fd,'rb') as source:
            info=os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or (info.st_uid,info.st_gid)!=(uid,gid) or stat.S_IMODE(info.st_mode)!=0o600:
                raise ValueError('Credential files must already be private 0600 with approved ownership')
            value=source.read(1025).strip()
            if info.st_size>1024:raise ValueError('Invalid credential length')
            OwnerAuth(value.decode('ascii'))
            if not value:raise ValueError('Empty credential')
            tokens.append(value)
    if tokens[0]==tokens[1]:raise ValueError('Owner and worker credentials must be distinct')
    if shutil.disk_usage(root).free<205*GB:raise ValueError('At least 205 GB free required for the 200 GB reserve and initial headroom')
    return {'layout':'pass','free_space':'pass','credential_metadata':'pass','mutations':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('review_env',type=Path)
    args=parser.parse_args(argv)
    try:
        root,uid,gid=validate_settings(read_settings(args.review_env))
        result=inspect_layout(root,uid,gid)
    except (ValueError,OSError):
        print(json.dumps({'ready':False,'error':'Review values, existing private layout, ownership, token metadata and free storage; no changes made'}));return 2
    print(json.dumps({'ready':False,'preflight':result,'remaining':['Docker/Compose and image inspection','listener/Serve/ACL review','storage quota','approved installation and end-to-end verification']}));return 0

if __name__=='__main__':raise SystemExit(main())
