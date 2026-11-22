"""Offline authenticated-encrypted recovery bundles, bounded to 64 MiB plaintext.

Optional operator tool; never imported by the stdlib backend. No plaintext staging archive,
credential collection, key backup, Git execution, unsafe extraction or existing-path overwrite.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import sqlite3
import stat
import tarfile
import time
from . import maintenance,runtime,secure_files,security

MAX_ARCHIVE=secure_files.MAX_BYTES
MAX_CIPHERTEXT=MAX_ARCHIVE*2


def fernet(key_file):
    try:from cryptography.fernet import Fernet
    except ImportError:raise ValueError('Optional reviewed recovery cryptography dependency unavailable') from None
    return Fernet(secure_files.read_regular(key_file,128,private=True).strip())


def digest(data):return hashlib.sha256(data).hexdigest()


def private_parents(target,path):
    """Create every missing parent of ``path`` with mode 0o700.

    ``Path.mkdir(parents=True,mode=0o700)`` applies that mode to the final component only and
    leaves the ancestors it creates at 0o777 & ~umask, which would expose the restored
directory structure to other local accounts.
    """
    current=target
    for part in path.relative_to(target).parts[:-1]:
        current=current/part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise ValueError('Restore path contains a non-directory component')
        current.mkdir(mode=0o700,exist_ok=True)
    return path.parent


def data_root(value):
    root=secure_files.reviewed_scope(value);secure_files.no_symlink_parents(root)
    info=root.stat()
    if not root.is_dir() or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('Recovery requires an existing private owned data directory')
    return root


def relocate(connection,old,new):
    for table,parent in (('projects','projects'),('workspaces','workspaces')):
        for rowid,value in connection.execute(f'SELECT rowid,path FROM {table}').fetchall():
            try:relative=PurePosixPath(value).relative_to(PurePosixPath(str(old))/parent)
            except (ValueError,TypeError):raise ValueError('Database references storage outside dedicated project/workspace roots') from None
            if str(relative)!='.':secure_files.canonical_name(str(relative))
            target=str(new/parent) if str(relative)=='.' else str(new/parent/str(relative))
            connection.execute(f'UPDATE {table} SET path=? WHERE rowid=?',(target,rowid))


def database_bytes(path,old,new=None):
    secure_files.no_symlink_parents(path)
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>MAX_ARCHIVE:raise ValueError('Database exceeds recovery scope')
    source=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);destination=sqlite3.connect(':memory:')
    try:
        source.execute('PRAGMA trusted_schema=OFF');source.backup(destination)
        if destination.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('Database integrity failed')
        relocate(destination,old,new or old);destination.commit()
        value=destination.serialize()
        if len(value)>MAX_ARCHIVE:raise ValueError('Database exceeds recovery byte budget')
        return value
    finally:source.close();destination.close()


def encode(entries,manifest,key_file):
    if len(entries)>secure_files.MAX_FILES or sum(map(len,entries.values()))>MAX_ARCHIVE:raise ValueError('Recovery content exceeds 64 MiB; no partial backup is created')
    manifest={**manifest,'version':1,'files':{name:{'bytes':len(value),'sha256':digest(value)} for name,value in entries.items()}}
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as archive:
        for name,value in {'manifest.json':json.dumps(manifest,sort_keys=True).encode(),**entries}.items():
            secure_files.canonical_name(name);item=tarfile.TarInfo(name);item.size=len(value);item.mode=0o600
            archive.addfile(item,io.BytesIO(value))
            if buffer.tell()>MAX_ARCHIVE:raise ValueError('Archive overhead exceeds recovery budget')
    if buffer.tell()>MAX_ARCHIVE:raise ValueError('Archive exceeds recovery budget')
    return fernet(key_file).encrypt(buffer.getvalue())


def decode(payload,key_file):
    if len(payload)>MAX_CIPHERTEXT:raise ValueError('Encrypted bundle exceeds recovery budget')
    try:plain=fernet(key_file).decrypt(payload)
    except Exception:raise ValueError('Recovery authentication failed; no output created') from None
    if len(plain)>MAX_ARCHIVE:raise ValueError('Decrypted archive exceeds recovery budget')
    entries={};total=0
    try:
        with tarfile.open(fileobj=io.BytesIO(plain),mode='r:') as archive:
            for member in archive:
                secure_files.canonical_name(member.name)
                if not member.isfile() or member.size<0 or member.size>MAX_ARCHIVE or member.pax_headers or member.name in entries:raise ValueError('Duplicate, linked or unsupported recovery entry')
                total+=member.size
                if total>MAX_ARCHIVE or len(entries)>=secure_files.MAX_FILES+1:raise ValueError('Recovery manifest budget exceeded')
                source=archive.extractfile(member);value=source.read(member.size+1)
                if len(value)!=member.size:raise ValueError('Truncated recovery entry')
                entries[member.name]=value
    except (tarfile.TarError,OSError):raise ValueError('Invalid recovery archive') from None
    try:manifest=json.loads(entries.pop('manifest.json'),object_pairs_hook=security.unique_json_object)
    except (KeyError,ValueError):raise ValueError('Recovery manifest missing or invalid') from None
    if not isinstance(manifest,dict) or set(manifest)!={'version','source_data','created_at','files','configuration','credentials','scope'} or manifest['version']!=1:
        raise ValueError('Unsupported recovery manifest')
    if not isinstance(manifest['files'],dict) or set(manifest['files'])!=set(entries):raise ValueError('Recovery inventory mismatch')
    for name,value in entries.items():
        if any(str(parent) in entries for parent in PurePosixPath(name).parents):raise ValueError('File/directory recovery collision')
        if not (name in {'data/personal_codex.db','release.zip'} or name.startswith(('data/projects/','data/workspaces/'))):raise ValueError('Entry outside recovery scope')
        if manifest['files'][name]!={'bytes':len(value),'sha256':digest(value)}:raise ValueError('Recovery content digest mismatch')
    if 'data/personal_codex.db' not in entries or 'release.zip' not in entries:raise ValueError('Database or source release missing')
    return entries,manifest


def checkpoint(data,destination,key_file,release_zip,configuration=None):
    started=time.monotonic();root=data_root(data);destination=Path(destination).absolute();key=Path(key_file).absolute()
    if key==root or root in key.parents:raise ValueError('Keep the recovery key outside application data and backups')
    secure_files.no_symlink_parents(destination.parent)
    if destination.exists() or destination.is_symlink():raise FileExistsError('Recovery destination already exists')
    with runtime.InstanceLock(root):
        entries={'data/personal_codex.db':database_bytes(root/'personal_codex.db',root),
                 'release.zip':secure_files.read_regular(release_zip,MAX_ARCHIVE)}
        remaining=MAX_ARCHIVE-sum(map(len,entries.values()))
        for name in ('projects','workspaces'):
            folder=root/name
            if folder.exists() or folder.is_symlink():
                files=secure_files.read_tree(folder,max_bytes=remaining)
                entries.update({'data/'+name+'/'+path:value for path,value in files.items()});remaining-=sum(map(len,files.values()))
        config=configuration or {}
        if set(config)-{'PC_ROOT','PC_UID','PC_GID','PC_IMAGE','PC_ORIGIN'} or any(not isinstance(v,str) for v in config.values()):
            raise ValueError('Recovery accepts only the five nonsecret deployment settings')
        payload=encode(entries,{'source_data':str(root),'created_at':int(time.time()),'configuration':config,
                               'credentials':'excluded; rotate owner/worker credentials and reconnect; recovery key stored separately',
                               'scope':'offline DB + dedicated project/workspace files + source release; no images/models/secrets/external paths'},key_file)
        maintenance.require_capacity(root,len(payload))
        if shutil.disk_usage(destination.parent).free-len(payload)<maintenance.policy()['reserve_bytes']:raise ValueError('Recovery output would cross free-space reserve')
        secure_files.write_new(destination,payload)
    return {'bytes':len(payload),'sha256':digest(payload),'files':len(entries),'encrypted':True,'elapsed_ms':int((time.monotonic()-started)*1000),'quiescent_backend':True,'automatic_deletion':False}


def restore(bundle,destination,key_file):
    started=time.monotonic();target=Path(destination).absolute();secure_files.no_symlink_parents(target.parent)
    if target.exists() or target.is_symlink():raise FileExistsError('Restore requires a completely new destination')
    payload=secure_files.read_regular(bundle,MAX_CIPHERTEXT,private=True)
    entries,manifest=decode(payload,key_file)
    old=manifest['source_data']
    if not isinstance(old,str) or not old.startswith('/'):raise ValueError('Invalid source data root')
    db=sqlite3.connect(':memory:')
    try:
        db.deserialize(entries['data/personal_codex.db']);db.execute('PRAGMA trusted_schema=OFF')
        if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('Restored database integrity failed')
        relocate(db,old,target/'data')
        revoked=db.execute("UPDATE approvals SET status='revoked' WHERE status IN ('pending','approved')").rowcount
        db.execute("UPDATE operations SET status='interrupted',error=? WHERE status='running'",('Restored checkpoint; operation not replayed',))
        db.execute("UPDATE proposals SET status='interrupted' WHERE status IN ('pending','executing')")
        db.execute("UPDATE rounds SET status='interrupted',error=? WHERE status IN ('awaiting-approval','executing')",('Restored checkpoint; fresh review required',))
        db.execute("UPDATE tasks SET status='needs-another-round' WHERE status NOT IN ('completed','cancelled')")
        db.execute("UPDATE workspaces SET status='recovery-review' WHERE status='ready'")
        db.execute("UPDATE messages SET status='stopped',error=? WHERE status IN ('queued','streaming')",('Restored checkpoint; partial text is display-only',))
        db.execute("UPDATE inference_jobs SET status=CASE WHEN status IN ('queued','running') THEN 'interrupted' ELSE status END,prompt='',content='',lease_hash=NULL")
        db.execute('UPDATE inference_workers SET last_seen=0')
        db.commit();entries['data/personal_codex.db']=db.serialize()
    finally:db.close()
    # All authentication, inventory, digest, path and SQLite checks complete before directory creation.
    size=sum(map(len,entries.values()))
    if shutil.disk_usage(target.parent).free-size<maintenance.policy()['reserve_bytes']:raise ValueError('Restore would cross free-space reserve')
    target.mkdir(mode=0o700)
    (target/'data').mkdir(mode=0o700)
    marker={'execution_disabled':True,'source_bundle_sha256':digest(payload),
            'requires':['review project/worktree Git pointers before any Git execution','fresh owner/worker credentials','review relocated settings/native URL','backend startup recovery; never replay jobs'],'restored_at':int(time.time())}
    secure_files.write_new(target/'data'/'RECOVERY_LOCKED.json',json.dumps(marker,indent=2).encode())
    try:
        for name,value in entries.items():
            path=target/name;private_parents(target,path);secure_files.write_new(path,value)
        for name in ('projects','workspaces'):(target/'data'/name).mkdir(exist_ok=True,mode=0o700)
        secure_files.write_new(target/'configuration.review.json',json.dumps(manifest['configuration'],indent=2).encode())
        secure_files.write_new(target/'data'/'RECOVERY_COMPLETE.json',json.dumps({'source_bundle_sha256':digest(payload),'complete':True}).encode())
    except Exception:
        # Retain our partial new tree for operator inspection. Never remove an existing backup.
        raise ValueError('Restore incomplete; new private output retained for inspection, never start it') from None
    return {'files':len(entries),'database_integrity':'ok','execution_disabled':True,'credentials_restored':False,
            'elapsed_ms':int((time.monotonic()-started)*1000),'revoked_approvals':revoked,'recovery_point':manifest['created_at'],'git_repair_requires_review':True}
