"""Operator-only container job contract. Never grants backend execution or Docker authority.

Requests carry a bounded copy of source over stdin: no host project, home, API credential,
Docker socket, device or writable host mount is available to the untrusted process.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid
from . import secure_files,security

MAX_INPUT=8*1024*1024
MAX_REQUEST=12*1024*1024
MAX_OUTPUT=200_000
MAX_FILES=2000


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def secret_name(value):
    name=value.casefold()
    return (name in {'.ssh','.aws','.docker','.codex','.npmrc','.pypirc','.netrc','secrets','credentials.json','owner-token','worker-token','id_rsa','id_ed25519'}
            or name.startswith('.env') or name.endswith(('.pem','.key','.p12','.pfx')))


def tree_digest(files):return sha(canonical({name:{'bytes':len(value),'sha256':sha(value)} for name,value in sorted(files.items())}))


def request(source,argv,timeout=30):
    source=secure_files.reviewed_scope(source)
    files=secure_files.read_tree(source,max_bytes=MAX_INPUT,max_files=MAX_FILES,exclude_git=True,reject_name=secret_name)
    value={'version':1,'id':str(uuid.uuid4()),'argv':argv,'timeout_seconds':timeout,'files':{name:base64.b64encode(data).decode() for name,data in files.items()},'tree_sha256':tree_digest(files)}
    value['request_sha256']=sha(canonical(value));validate(value)
    return value


def validate(value):
    if not isinstance(value,dict) or set(value)!={'version','id','argv','timeout_seconds','files','tree_sha256','request_sha256'} or type(value['version']) is not int or value['version']!=1:
        raise ValueError('Unknown isolated job schema')
    try:
        if not isinstance(value['id'],str) or str(uuid.UUID(value['id'],version=4))!=value['id']:raise ValueError('Invalid job UUID')
    except (ValueError,TypeError,AttributeError):raise ValueError('Invalid job UUID') from None
    command=value['argv']
    if (not isinstance(command,list) or not 3<=len(command)<=64 or command[:3]!=['python3','-m','unittest']
            or any(not isinstance(arg,str) or not arg or len(arg)>512 or '\x00' in arg for arg in command)):
        raise ValueError('Prototype supports only explicitly reviewed Python unittest argv')
    if type(value['timeout_seconds']) is not int or not 1<=value['timeout_seconds']<=120:raise ValueError('Isolated job timeout outside budget')
    if not isinstance(value['files'],dict) or len(value['files'])>MAX_FILES:raise ValueError('Isolated source inventory exceeds budget')
    files={};size=0
    for name,text in value['files'].items():
        relative=secure_files.canonical_name(name)
        if any(secret_name(part) or part in {'.git','personal-codex-diagnostic.txt'} for part in relative.parts):raise ValueError('Excluded source path')
        if any(str(parent) in value['files'] for parent in relative.parents):raise ValueError('Source file/directory collision')
        if not isinstance(text,str) or len(text)>MAX_REQUEST:raise ValueError('Invalid source encoding')
        try:content=base64.b64decode(text,validate=True)
        except ValueError:raise ValueError('Invalid source encoding') from None
        size+=len(content)
        if size>MAX_INPUT:raise ValueError('Isolated source byte budget exceeded')
        files[name]=content
    if tree_digest(files)!=value['tree_sha256'] or sha(canonical({k:v for k,v in value.items() if k!='request_sha256'}))!=value['request_sha256']:
        raise ValueError('Isolated job/source digest mismatch')
    if len(canonical(value))>MAX_REQUEST:raise ValueError('Isolated request byte budget exceeded')
    return files


def read_request(path):
    value=json.loads(secure_files.read_regular(path,MAX_REQUEST,private=True),object_pairs_hook=security.unique_json_object)
    validate(value);return value


def docker_argv(value,image,uid,gid,daemon_socket,docker='/usr/bin/docker'):
    validate(value)
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',image):raise ValueError('Reviewed local immutable executor image ID required')
    if any(type(number) is not int or not 0<number<10**9 for number in (uid,gid)):raise ValueError('Approved non-root UID/GID required')
    allowed_sockets={'/var/run/docker.sock','/run/docker.sock',f'/run/user/{uid}/docker.sock'}
    if daemon_socket not in allowed_sockets or not Path(docker).is_absolute() or Path(docker).name!='docker':raise ValueError('Only explicit reviewed local Docker authority is supported')
    return [docker,'--host','unix://'+daemon_socket,'run','--rm','--pull','never','--platform','linux/amd64',
            '--name','personal-codex-job-'+value['id'],'--label','local.personalcodex.job='+value['id'],
            '--network','none','--ipc','none','--cgroupns','private','--read-only','--user',f'{uid}:{gid}',
            '--cap-drop','ALL','--security-opt','no-new-privileges:true','--security-opt','apparmor=docker-default',
            '--pids-limit','64','--cpus','1','--memory','768m','--memory-swap','768m','--ulimit','nofile=128:128','--ulimit','core=0:0',
            '--log-driver','none','--no-healthcheck','--restart','no','--stop-timeout','2',
            '--tmpfs',f'/workspace:rw,nosuid,nodev,noexec,size=268435456,uid={uid},gid={gid},mode=0700',
            '--tmpfs',f'/tmp:rw,nosuid,nodev,noexec,size=16777216,uid={uid},gid={gid},mode=0700',
            '--env','HOME=/tmp','--env','PYTHONDONTWRITEBYTECODE=1','--env','PYTHONNOUSERSITE=1',
            '--workdir','/workspace','--entrypoint','/usr/local/bin/python3','--interactive',image,'/opt/personal-codex/scripts/isolated_executor.py']


def runtime_checks():
    import platform
    if platform.system()!='Linux':return {'linux':False}
    def read(path):
        try:return Path(path).read_text()[:65536]
        except OSError:return ''
    status={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in read('/proc/self/status').splitlines() if ':' in line}
    mounts=[line.split() for line in read('/proc/mounts').splitlines()]
    checks={'linux':True,'nonroot':os.getuid()!=0,'seccomp_filter':status.get('Seccomp')=='2','no_new_privileges':status.get('NoNewPrivs')=='1',
            'zero_capabilities':all(status.get(name)=='0000000000000000' for name in ('CapEff','CapPrm','CapBnd')),
            'apparmor':read('/proc/self/attr/current').strip()=='docker-default (enforce)',
            'private_network':set(os.listdir('/sys/class/net'))=={'lo'},
            'readonly_root':bool(os.statvfs('/').f_flag&os.ST_RDONLY),
            'memory_limit':read('/sys/fs/cgroup/memory.max').strip()=='805306368',
            'no_swap':read('/sys/fs/cgroup/memory.swap.max').strip()=='0',
            'pid_limit':read('/sys/fs/cgroup/pids.max').strip()=='64',
            'cpu_limit':read('/sys/fs/cgroup/cpu.max').strip()=='100000 100000'}
    maps=[line.split() for line in read('/proc/self/uid_map').splitlines()]
    checks['user_namespace']=any(len(row)==3 and row[0]=='0' and row[1]!='0' for row in maps)
    for name,maximum in (('/workspace',268435456),('/tmp',16777216)):
        checks[name+'_tmpfs']=any(len(row)>3 and row[1]==name and row[2]=='tmpfs' for row in mounts)
        try:checks[name+'_size']=os.statvfs(name).f_blocks*os.statvfs(name).f_frsize<=maximum
        except OSError:checks[name+'_size']=False
    return checks
