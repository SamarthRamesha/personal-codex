"""Bounded descriptor-relative file snapshots. No following links or executing Git/configuration."""
from __future__ import annotations
import os
from pathlib import Path,PurePosixPath
import stat

MAX_BYTES=64*1024*1024
MAX_FILES=10_000


def canonical_name(name):
    if (not isinstance(name,str) or not name or len(name)>1024 or '\\' in name or '\x00' in name
            or any(ord(c)<32 or ord(c)==127 or '\u202a'<=c<='\u202e' or '\u2066'<=c<='\u2069' for c in name)
            or name.startswith('/') or any(part in ('','.','..') for part in name.split('/'))):
        raise ValueError('Noncanonical archive or snapshot path')
    return PurePosixPath(name)


def no_symlink_parents(path):
    for item in (path,*path.parents):
        if item.is_symlink():raise ValueError('Snapshot path contains a symlink')


def identity(info):return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_nlink)


def read_regular(path,limit=MAX_BYTES,private=False):
    path=Path(path).absolute();no_symlink_parents(path)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit:raise ValueError('Unsupported file or byte limit exceeded')
        if private and (before.st_uid!=os.getuid() or stat.S_IMODE(before.st_mode)!=0o600):raise ValueError('Private file must be owner-only 0600')
        chunks=[];size=0
        while True:
            block=os.read(fd,min(65536,limit+1-size))
            if not block:break
            size+=len(block)
            if size>limit:raise ValueError('File byte limit exceeded')
            chunks.append(block)
        if identity(before)!=identity(os.fstat(fd)):raise ValueError('File changed during snapshot')
        return b''.join(chunks)
    finally:os.close(fd)


def read_tree(root,*,max_bytes=MAX_BYTES,max_files=MAX_FILES,exclude_git=False,reject_name=None):
    root=Path(root).absolute();no_symlink_parents(root);result={};total=0
    flags=os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0)
    base=os.open(root,flags)
    def walk(directory,prefix=''):
        nonlocal total
        before=os.fstat(directory)
        with os.scandir(directory) as entries:
            for entry in entries:
                name=entry.name
                if name=='personal-codex-diagnostic.txt':raise ValueError('Protected diagnostic is excluded; no file was read')
                if exclude_git and name=='.git':continue
                if reject_name and reject_name(name):raise ValueError('Excluded snapshot filename')
                relative=prefix+name;canonical_name(relative)
                info=os.stat(name,dir_fd=directory,follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    child=os.open(name,flags,dir_fd=directory)
                    try:
                        if (info.st_dev,info.st_ino)!=(os.fstat(child).st_dev,os.fstat(child).st_ino):raise ValueError('Directory replaced during snapshot')
                        walk(child,relative+'/')
                    finally:os.close(child)
                elif stat.S_ISREG(info.st_mode):
                    if len(result)>=max_files or total+info.st_size>max_bytes or info.st_nlink!=1:raise ValueError('Snapshot budget or alias policy exceeded')
                    fd=os.open(name,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0),dir_fd=directory)
                    try:
                        opened=os.fstat(fd)
                        if identity(info)!=identity(opened):raise ValueError('File replaced during snapshot')
                        content=[];size=0
                        while True:
                            block=os.read(fd,min(65536,max_bytes-total-size+1))
                            if not block:break
                            size+=len(block)
                            if total+size>max_bytes:raise ValueError('Snapshot byte budget exceeded')
                            content.append(block)
                        if identity(opened)!=identity(os.fstat(fd)):raise ValueError('File changed during snapshot')
                        result[relative]=b''.join(content);total+=size
                    finally:os.close(fd)
                else:raise ValueError('Symlink, device, socket or special file is not snapshot eligible')
        after=os.fstat(directory)
        if (before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns):
            raise ValueError('Directory changed during snapshot')
    try:walk(base)
    finally:os.close(base)
    return dict(sorted(result.items()))


def write_new(path,content):
    path=Path(path);no_symlink_parents(path.parent)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(content);stream.flush();os.fsync(stream.fileno())
    except BaseException:
        # Only our newly created incomplete output is eligible for cleanup, never an existing file.
        path.unlink(missing_ok=True);raise


def reviewed_scope(path):
    """Reject known broad/family/other-app roots before inventory or file access."""
    path=Path(path).expanduser().absolute()
    if '..' in path.parts or path in {Path('/'),Path.home(),Path('/Users'),Path('/home'),Path('/DATA'),Path('/DATA/AppData')}:
        raise ValueError('Broad personal/shared storage is outside the reviewed application scope')
    for forbidden in (Path('/DATA/Backup'),Path('/DATA/Gallery')):
        if path==forbidden or forbidden in path.parents:raise ValueError('Family storage is outside application scope')
    applications=Path('/DATA/AppData');dedicated=applications/'PersonalCodex'
    if applications in path.parents and not (path==dedicated or dedicated in path.parents):
        raise ValueError('Existing application storage is outside Personal Codex scope')
    return path
