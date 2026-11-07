"""Claim-before-inference replay journal. Metadata only; never stores prompts or credentials."""
from __future__ import annotations
import os
from pathlib import Path
import sqlite3
import stat
import threading
import time

MAX_CLAIMS=10_000


class ReplayError(ValueError):pass


class ReplayJournal:
    def __init__(self,directory=None):
        self.lock=threading.RLock()
        if directory is None:
            self.connection=sqlite3.connect(':memory:',check_same_thread=False)
        else:
            root=Path(directory).expanduser().absolute()
            for item in (root,*root.parents):
                if item.is_symlink():raise ReplayError('Worker state path must not contain symlinks')
            info=root.stat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
                raise ReplayError('Worker state needs an existing private owner-only 0700 directory')
            path=root/'inference-claims.sqlite3'
            fd=os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
            try:
                info=os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600:
                    raise ReplayError('Worker journal must be a private regular file without aliases')
            finally:os.close(fd)
            self.connection=sqlite3.connect(path,check_same_thread=False,timeout=5)
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, model TEXT NOT NULL, prompt_sha256 TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL)')
        self.connection.commit()

    def claim(self,job):
        with self.lock:
            try:
                self.connection.execute('BEGIN IMMEDIATE')
                if self.connection.execute('SELECT 1 FROM claims WHERE id=?',(job['id'],)).fetchone():
                    raise ReplayError('Inference job was already claimed; no model invocation replayed')
                if self.connection.execute('SELECT COUNT(*) FROM claims').fetchone()[0]>=MAX_CLAIMS:
                    raise ReplayError('Worker replay-journal budget exhausted; reviewed archival required')
                self.connection.execute('INSERT INTO claims VALUES (?,?,?,?,?)',(job['id'],job['model'],job['prompt_sha256'],'claimed',int(time.time())))
                self.connection.commit()  # Must be durable before invoking Ollama, even after an ambiguous response.
            except Exception:self.connection.rollback();raise

    def finish(self,jid,status):
        if status not in {'complete','failed'}:raise ReplayError('Invalid worker outcome')
        with self.lock:
            self.connection.execute('UPDATE claims SET status=? WHERE id=?',(status,jid));self.connection.commit()

    def close(self):
        with self.lock:self.connection.close()
