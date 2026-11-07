import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from app import server,maintenance


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.old=server.DATA,server.DB_PATH
        server.DATA=self.root/'data';server.DB_PATH=server.DATA/'test.db'
        self.store=server.Store()
        self.store.write('INSERT INTO projects VALUES (?,?,?,?)',('p','Fixture','/synthetic',1))
        self.policy=patch.dict(os.environ,{'PERSONAL_CODEX_RESERVE_GB':'1','PERSONAL_CODEX_STORAGE_GB':'75'});self.policy.start()
    def tearDown(self):
        self.store.conn.close();server.DATA,server.DB_PATH=self.old;self.policy.stop();self.tmp.cleanup()
    def test_snapshot_restore_integrity_and_original_preservation(self):
        result=maintenance.snapshot(self.store,server.DATA,server.DB_PATH)
        self.assertEqual(result['integrity'],'ok')
        path=server.DATA/'backups'/result['filename']
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        restored=self.root/'restored.sqlite3';maintenance.restore_new(path,restored)
        connection=sqlite3.connect(restored)
        self.assertEqual(connection.execute('SELECT name FROM projects').fetchone()[0],'Fixture');connection.close()
        with self.assertRaises(FileExistsError):maintenance.restore_new(path,restored)
        self.assertEqual(self.store.one('SELECT name FROM projects')['name'],'Fixture')
    def test_reserve_budget_and_retention_refuse_without_deleting_anything(self):
        with patch.object(maintenance.shutil,'disk_usage',return_value=type('Usage',(),{'free':500,'total':1000})()):
            with self.assertRaisesRegex(ValueError,'safety reserve'):maintenance.snapshot(self.store,server.DATA,server.DB_PATH)
        target=server.DATA/'backups';target.mkdir(exist_ok=True)
        for n in range(7):(target/f'snapshot-{n}.sqlite3').write_text('retained')
        with self.assertRaisesRegex(ValueError,'Seven snapshots'):maintenance.snapshot(self.store,server.DATA,server.DB_PATH)
        self.assertEqual(len(list(target.glob('snapshot-*'))),7)
        with patch.object(maintenance,'diagnostics',return_value={'storage':{'measurement_complete':True,'free_bytes':10**12,'reserve_bytes':1,'managed_bytes':99,'budget_bytes':100}}):
            with self.assertRaisesRegex(ValueError,'budget'):maintenance.require_capacity(server.DATA,2)
    def test_corruption_and_symlinks_are_refused(self):
        corrupt=self.root/'corrupt';corrupt.write_text('not a database')
        destination=self.root/'new.db'
        with self.assertRaises((ValueError,sqlite3.Error)):maintenance.restore_new(corrupt,destination)
        self.assertFalse(destination.exists())
        outside=self.root/'external';outside.mkdir();(outside/'untouched').write_text('family fixture')
        (server.DATA/'backups').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):maintenance.snapshot(self.store,server.DATA,server.DB_PATH)
        self.assertEqual(list(outside.iterdir()),[outside/'untouched'])
    def test_own_data_measurement_never_traverses_external_symlink(self):
        outside=self.root/'outside';outside.mkdir();(outside/'data').write_bytes(b'x'*100000)
        baseline=maintenance.owned_bytes(server.DATA)[0]
        (server.DATA/'link').symlink_to(outside,target_is_directory=True)
        self.assertEqual(maintenance.owned_bytes(server.DATA)[0],baseline)
