"""Bounded own-data diagnostics and verified SQLite snapshots; never cleans shared storage."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile
import time
import threading

GB=1_000_000_000
MAX_OWN_FILES=100_000
SNAPSHOT_LOCK=threading.Lock()


def owned_bytes(root: Path) -> tuple[int,bool]:
    total=0;count=0;complete=True;started=time.monotonic()
    if root.is_symlink() or not root.is_dir():return 0,False
    def failed(_error):
        nonlocal complete
        complete=False
    for current, directories, files in os.walk(root,followlinks=False,onerror=failed):
        count+=len(directories)
        if count>MAX_OWN_FILES or time.monotonic()-started>2:return total,False
        directories[:]=[name for name in directories if not (Path(current)/name).is_symlink()]
        for name in files:
            count+=1
            if count>MAX_OWN_FILES or time.monotonic()-started>2:return total,False
            try:
                info=(Path(current)/name).lstat()
                if stat.S_ISREG(info.st_mode):total+=info.st_size
            except OSError:complete=False
    return total,complete


def policy() -> dict:
    def number(name,default):
        try:value=int(os.getenv(name,str(default)))
        except ValueError:raise ValueError(f'{name} must be a positive integer') from None
        if value<1 or value>100_000:raise ValueError(f'{name} is outside its supported range')
        return value*GB
    return {'reserve_bytes':number('PERSONAL_CODEX_RESERVE_GB',5 if sys.platform=='darwin' else 200),
            'budget_bytes':number('PERSONAL_CODEX_STORAGE_GB',75)}


def diagnostics(data: Path) -> dict:
    limits=policy();usage=shutil.disk_usage(data);size,complete=owned_bytes(data)
    reasons=[]
    if usage.free<limits['reserve_bytes']:reasons.append('free storage is below the configured safety reserve')
    elif usage.free<limits['reserve_bytes']+5*GB:reasons.append('free storage is approaching the safety reserve')
    if size>=limits['budget_bytes']:reasons.append('Personal Codex data exceeds its storage budget')
    elif size>=int(limits['budget_bytes']*.8):reasons.append('Personal Codex data is approaching its storage budget')
    if not complete:reasons.append('managed file inventory incomplete or limit reached; usage is a lower bound')
    return {'storage':{**limits,'free_bytes':usage.free,'total_bytes':usage.total,'managed_bytes':size,'measurement_complete':complete,
                       'scope':'Personal Codex data directory only; externally managed Ollama models are not included','warnings':reasons},
            'cpu':{'count':os.cpu_count(),'load_average':list(os.getloadavg()) if hasattr(os,'getloadavg') else None},
            'backups':{'count':len(list((data/'backups').glob('snapshot-*.sqlite3'))),'automatic_deletion':False},
            'telemetry':False,'cloud_fallback':False,
            'storage_enforcement':{'write_admission':enforce_enabled(),'inventory_cache_seconds':ADMISSION_TTL,'admission_margin_bytes':ADMISSION_MARGIN,
                                   'main_db_max_mib':os.getenv('PERSONAL_CODEX_DB_MAX_MIB','1024') if enforce_enabled() else None,'hard_filesystem_quota':False}}


def require_capacity(data: Path, additional: int):
    report=diagnostics(data)['storage']
    if not report['measurement_complete']:raise ValueError('Cannot verify managed-storage budget; snapshot refused')
    if report['free_bytes']-additional<report['reserve_bytes']:raise ValueError('Snapshot would cross the safety reserve')
    if report['managed_bytes']+additional>report['budget_bytes']:raise ValueError('Snapshot would cross the Personal Codex storage budget')


def verify_database(path: Path) -> None:
    if not path.is_file() or path.is_symlink():raise ValueError('Snapshot must be a regular file')
    connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        if connection.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('SQLite integrity check failed')
        tables={row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'projects','tasks','conversations','messages','approvals'}.issubset(tables):raise ValueError('Not a Personal Codex database')
    finally:connection.close()


def snapshot(store,data: Path,db_path: Path) -> dict:
    if not SNAPSHOT_LOCK.acquire(blocking=False):raise ValueError('A snapshot is already in progress')
    try:return _snapshot(store,data,db_path)
    finally:SNAPSHOT_LOCK.release()


def _snapshot(store,data: Path,db_path: Path) -> dict:
    target=data/'backups'
    if target.is_symlink():raise ValueError('Backup directory must not be a symlink')
    target.mkdir(mode=0o700,exist_ok=True)
    if len(list(target.glob('snapshot-*.sqlite3')))>=7:raise ValueError('Seven snapshots retained; archive an old Personal Codex snapshot explicitly before creating another')
    estimate=max(db_path.stat().st_size*2,1_048_576)
    require_capacity(data,estimate)
    fd,name=tempfile.mkstemp(prefix='.snapshot-',suffix='.partial',dir=target);os.close(fd);temporary=Path(name)
    started=time.monotonic()
    try:
        destination=sqlite3.connect(temporary)
        try:
            def progress(status, remaining, total):
                if time.monotonic()-started>30:raise ValueError('Snapshot exceeded its 30 second time budget')
                if shutil.disk_usage(data).free < policy()['reserve_bytes']:
                    raise ValueError('Snapshot stopped before crossing the safety reserve')
            with store.lock:store.conn.backup(destination,pages=128,sleep=.01,progress=progress)
        finally:destination.close()
        verify_database(temporary)
        size=temporary.stat().st_size
        require_capacity(data,size)
        hasher=hashlib.sha256()
        with temporary.open('rb') as source:
            for block in iter(lambda:source.read(1_048_576),b''):hasher.update(block)
        digest=hasher.hexdigest()
        filename=f'snapshot-{time.time_ns()}.sqlite3';final=target/filename
        # Atomic, no-overwrite publication; private temp file mode is preserved.
        os.link(temporary,final)
        return {'filename':filename,'bytes':size,'sha256':digest,'integrity':'ok','elapsed_ms':int((time.monotonic()-started)*1000)}
    finally:temporary.unlink(missing_ok=True)


def restore_new(source: Path,destination: Path) -> dict:
    """Restore into an explicitly new file. No live database or existing file is ever replaced."""
    verify_database(source)
    fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    try:
        original=sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)
        restored=sqlite3.connect(destination)
        try:original.backup(restored)
        finally:restored.close();original.close()
        verify_database(destination)
        return {'integrity':'ok','bytes':destination.stat().st_size}
    except Exception:
        destination.unlink(missing_ok=True)
        raise

# Application admission, not a filesystem quota. The DB page cap separately bounds the main DB.
ADMISSION_LOCK=threading.RLock()
ADMISSION_CACHE={}
ADMISSION_TTL=1.0
ADMISSION_MARGIN=3*GB


def enforce_enabled():return os.getenv('PERSONAL_CODEX_STORAGE_ENFORCE')=='1'


def admit_writes(data: Path):
    if not enforce_enabled():return
    try:from .secure_files import reviewed_scope
    except ImportError:from secure_files import reviewed_scope
    reviewed_scope(data)
    limits=policy();stamp=time.monotonic();key=(str(data),limits['reserve_bytes'],limits['budget_bytes'])
    with ADMISSION_LOCK:
        cached=ADMISSION_CACHE.get(key)
        if not cached or not 0<=stamp-cached[0]<=ADMISSION_TTL:
            report=diagnostics(data)['storage']
            if len(ADMISSION_CACHE)>=8:ADMISSION_CACHE.clear()
            ADMISSION_CACHE[key]=(time.monotonic(),report)
        else:report=cached[1]
        # Free space is cheap and checked on every admission, even when inventory is cached.
        free=shutil.disk_usage(data).free
        if (not report['measurement_complete'] or free<limits['reserve_bytes']+ADMISSION_MARGIN
                or report['managed_bytes']+ADMISSION_MARGIN>limits['budget_bytes']):
            raise ValueError('Storage write admission closed: reserve, allocation headroom or complete accounting unavailable')


def limit_database(connection):
    if not enforce_enabled():return
    try:maximum=int(os.getenv('PERSONAL_CODEX_DB_MAX_MIB','1024'))
    except ValueError:raise ValueError('Invalid main database page limit') from None
    if not 1<=maximum<=1024:raise ValueError('Main database limit must be 1–1024 MiB')
    page_size=connection.execute('PRAGMA page_size').fetchone()[0];pages=maximum*1024*1024//page_size
    if connection.execute('PRAGMA page_count').fetchone()[0]>pages:raise ValueError('Existing database exceeds reviewed page cap; no automatic shrink')
    if connection.execute(f'PRAGMA max_page_count={pages}').fetchone()[0]!=pages:raise ValueError('Database page cap unavailable')
