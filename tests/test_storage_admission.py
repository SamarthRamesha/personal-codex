"""Fail-closed application admission and a real SQLite page cap, not a filesystem quota."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from app import maintenance,server
import test_inference as fixtures


class StoragePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.addCleanup(self.tmp.cleanup)
        self.policy=patch.dict(os.environ,{'PERSONAL_CODEX_STORAGE_ENFORCE':'1','PERSONAL_CODEX_RESERVE_GB':'1'});self.policy.start();self.addCleanup(self.policy.stop)
        maintenance.ADMISSION_CACHE.clear()
    def report(self,**changes):
        return {'storage':{'measurement_complete':True,'managed_bytes':0,'free_bytes':10*maintenance.GB,'budget_bytes':75*maintenance.GB,'reserve_bytes':maintenance.GB,**changes}}
    def test_incomplete_or_near_allocation_inventory_closes_admission(self):
        for changes in ({'measurement_complete':False},{'managed_bytes':74*maintenance.GB}):
            maintenance.ADMISSION_CACHE.clear()
            with patch.object(maintenance,'diagnostics',return_value=self.report(**changes)):
                with self.assertRaisesRegex(ValueError,'admission closed'):maintenance.admit_writes(self.root)
    def test_free_space_is_rechecked_within_cache_window(self):
        with patch.object(maintenance,'diagnostics',return_value=self.report()) as diagnostic:
            with patch.object(maintenance.shutil,'disk_usage',return_value=type('U',(),{'free':10*maintenance.GB})()):maintenance.admit_writes(self.root)
            with patch.object(maintenance.shutil,'disk_usage',return_value=type('U',(),{'free':2*maintenance.GB})()):
                with self.assertRaises(ValueError):maintenance.admit_writes(self.root)
            self.assertEqual(diagnostic.call_count,1)
    def test_sqlite_main_database_cannot_grow_beyond_page_cap(self):
        path=self.root/'small.db';connection=sqlite3.connect(path)
        try:
            with patch.dict(os.environ,{'PERSONAL_CODEX_DB_MAX_MIB':'1'}):maintenance.limit_database(connection)
            connection.execute('CREATE TABLE payload (data BLOB)');connection.commit()
            with self.assertRaises(sqlite3.OperationalError):connection.execute('INSERT INTO payload VALUES (?)',(b'x'*(2*1024*1024),))
            self.assertLessEqual(path.stat().st_size,1024*1024)
        finally:connection.close()
    def test_directory_count_and_elapsed_inventory_are_bounded(self):
        with patch.object(maintenance,'MAX_OWN_FILES',2):
            for n in range(3):(self.root/str(n)).mkdir()
            self.assertFalse(maintenance.owned_bytes(self.root)[1])
        with patch.object(maintenance.time,'monotonic',side_effect=[0,3]):self.assertFalse(maintenance.owned_bytes(self.root)[1])


@unittest.skipUnless(os.getenv('PERSONAL_CODEX_HTTP_TESTS')=='1','requires explicitly enabled loopback listener')
class StorageHttpTests(unittest.TestCase):
    setUp=fixtures.WorkerHttpTests.setUp
    tearDown=fixtures.WorkerHttpTests.tearDown
    request=fixtures.WorkerHttpTests.request
    call=fixtures.WorkerHttpTests.call
    def test_mutations_fail_before_creation_but_read_auth_stop_and_rotation_remain_available(self):
        with patch.object(maintenance,'admit_writes',side_effect=ValueError('synthetic capacity closure')):
            self.assertEqual(self.call('/api/conversations',{'title':'must not persist'})[0],503)
            self.assertEqual(self.call('/api/worker/poll',{'models':['fixture']},True)[0],503)
            self.assertEqual(self.call('/api/conversations',method='GET')[0],200)
            self.assertEqual(self.call('/api/session',{'token':self.token})[0],200)
            self.assertEqual(self.call('/api/conversations/missing/messages/missing/stop',{})[0],404)
            self.assertEqual(self.call('/api/inference/reload-credential',{})[0],400)
        self.assertEqual(server.STORE.one('SELECT COUNT(*) AS n FROM conversations')['n'],0)
