"""Search only explicit project excerpts; verify attribution, rollback and removal."""
from http.client import HTTPConnection
import json
import sqlite3
import tempfile
import threading
from pathlib import Path
import unittest
from unittest.mock import patch
from app import documents, security, server


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.old=server.DATA,server.DB_PATH,server.STORE,server.AUTH
        server.DATA=self.root/'state';server.DB_PATH=server.DATA/'test.db';server.STORE=server.Store()
        self.store=server.STORE;server.AUTH=security.OwnerAuth('synthetic-documents-owner-00000000000')
        self.addCleanup(self.restore)
        self.project=server.uid();self.other=server.uid()
        for identifier in (self.project,self.other):
            path=self.root/identifier;path.mkdir()
            self.store.write('INSERT INTO projects VALUES (?,?,?,?)',(identifier,'synthetic',str(path),1))

    def restore(self):
        self.store.close();server.DATA,server.DB_PATH,server.STORE,server.AUTH=self.old

    def attachment(self,text='Amber deployment rule: keep the demo service private.',project=None,name='architecture.txt'):
        identifier=server.uid();self.store.write('INSERT INTO project_attachments VALUES (?,?,?,?,?,?)',(identifier,project or self.project,name,'local text extraction',text,1));return identifier

    def test_no_automatic_indexing_or_file_access(self):
        identifier=self.attachment()
        self.assertEqual(documents.search(self.store,self.project,'amber'),[])
        with patch('builtins.open',side_effect=AssertionError('no filesystem scan')):
            documents.index(self.store,self.project,identifier);hits=documents.search(self.store,self.project,'amber')
        self.assertEqual(hits[0]['attachment_id'],identifier)
        self.assertEqual(hits[0]['trust'],'untrusted-reference')

    def test_project_isolation_including_foreign_attachment(self):
        own=self.attachment();foreign=self.attachment(project=self.other)
        documents.index(self.store,self.project,own);documents.index(self.store,self.other,foreign)
        self.assertEqual([h['attachment_id'] for h in documents.search(self.store,self.project,'amber')],[own])
        with self.assertRaises(LookupError):documents.index(self.store,self.project,foreign)

    def test_chunk_hash_and_character_attribution(self):
        text='x '*500+'amber boundary condition '+ 'z '*500;identifier=self.attachment(text)
        documents.index(self.store,self.project,identifier);hits=documents.search(self.store,self.project,'amber')
        self.assertTrue(hits)
        for hit in hits:
            self.assertEqual(hit['excerpt'],text[hit['start_char']:hit['end_char']])
            self.assertEqual(hit['source_hash'],documents.digest(text))
            self.assertEqual(hit['start_char'],hit['chunk']*documents.CHUNK_STEP)

    def test_tampered_index_chunk_cannot_claim_valid_source_hash(self):
        identifier=self.attachment();documents.index(self.store,self.project,identifier)
        self.store.write("UPDATE document_chunks SET body='amber fabricated reference' WHERE attachment_id=?",(identifier,))
        self.assertEqual(documents.search(self.store,self.project,'amber'),[])

    def test_stale_sources_are_omitted_until_explicit_reindex(self):
        identifier=self.attachment();documents.index(self.store,self.project,identifier)
        self.store.write("UPDATE project_attachments SET excerpt='Violet replacement design' WHERE id=?",(identifier,))
        self.assertEqual(documents.search(self.store,self.project,'amber'),[])
        self.assertTrue(documents.listing(self.store,self.project)['documents'][0]['stale'])
        documents.index(self.store,self.project,identifier)
        self.assertEqual(documents.search(self.store,self.project,'amber'),[])
        self.assertTrue(documents.search(self.store,self.project,'violet'))

    def test_removal_stops_retrieval_but_retains_selected_attachment(self):
        identifier=self.attachment();documents.index(self.store,self.project,identifier)
        self.assertIn('UNTRUSTED',documents.prompt_block(self.store,self.project,'amber'))
        documents.remove(self.store,self.project,identifier)
        self.assertEqual(documents.prompt_block(self.store,self.project,'amber'),'')
        self.assertIsNotNone(self.store.one('SELECT id FROM project_attachments WHERE id=?',(identifier,)))

    def test_unsafe_or_oversized_excerpts_rejected_without_partial_rows(self):
        for value in ('password=synthetic-value','"api_key": "synthetic-value"','-----BEGIN PRIVATE KEY-----','amber\x00text','amber\u202etext',' ' , 'x'*(documents.MAX_CHARS+1)):
            with self.subTest(value=value[:20]):
                identifier=self.attachment(value)
                with self.assertRaises(ValueError):documents.index(self.store,self.project,identifier)
        self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM project_documents')['n'],0)

    def test_literal_queries_cannot_use_match_or_sql_syntax(self):
        identifier=self.attachment();documents.index(self.store,self.project,identifier)
        self.assertTrue(documents.search(self.store,self.project,'amber" OR project_id:*'))
        self.assertEqual(documents.search(self.store,self.other,'amber" OR project_id:*'),[])
        self.assertEqual(documents.search(self.store,self.project,"' OR 1=1 --"),[])
        for query,limit in [('',5),('x'*201,5),('amber',True),('amber',11)]:
            with self.assertRaises(ValueError):documents.search(self.store,self.project,query,limit)

    def test_reindex_rollback_preserves_previous_complete_index(self):
        identifier=self.attachment();documents.index(self.store,self.project,identifier)
        before=self.store.one('SELECT source_hash FROM project_documents WHERE attachment_id=?',(identifier,))['source_hash']
        self.store.write("CREATE TRIGGER refuse_reindex BEFORE INSERT ON project_documents BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):documents.index(self.store,self.project,identifier)
        self.assertEqual(self.store.one('SELECT source_hash FROM project_documents WHERE attachment_id=?',(identifier,))['source_hash'],before)
        self.assertTrue(documents.search(self.store,self.project,'amber'))

    def test_document_cap_and_same_source_reindex(self):
        with patch.object(documents,'MAX_DOCUMENTS',2):
            first,second,third=(self.attachment() for _ in range(3))
            documents.index(self.store,self.project,first);documents.index(self.store,self.project,second)
            documents.index(self.store,self.project,first)
            with self.assertRaises(ValueError):documents.index(self.store,self.project,third)
        self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM project_documents')['n'],2)

    def test_chunk_cap_is_atomic(self):
        first=self.attachment();second=self.attachment('amber '*300)
        with patch.object(documents,'MAX_CHUNKS',2):
            documents.index(self.store,self.project,first)
            with self.assertRaises(ValueError):documents.index(self.store,self.project,second)
        self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM project_documents')['n'],1)

    def test_deleted_or_renamed_attachment_is_not_fresh(self):
        identifier=self.attachment();documents.index(self.store,self.project,identifier)
        self.store.write("UPDATE project_attachments SET name='different.txt' WHERE id=?",(identifier,))
        self.assertEqual(documents.search(self.store,self.project,'amber'),[])
        self.store.write('DELETE FROM project_attachments WHERE id=?',(identifier,))
        self.assertTrue(documents.listing(self.store,self.project)['documents'][0]['stale'])

    def test_optional_fts_absence_does_not_disable_existing_memory(self):
        identifier=self.attachment()
        with patch.object(documents,'available',return_value=False):
            self.assertFalse(documents.listing(self.store,self.project)['available'])
            self.assertEqual(documents.search(self.store,self.project,'amber'),[])
            with self.assertRaises(ValueError):documents.index(self.store,self.project,identifier)
        self.assertEqual(server.memory_rows(self.project),[])

    def test_prompt_budget_keeps_attribution_and_delimiters(self):
        identifier=self.attachment('amber αβγ '*400);documents.index(self.store,self.project,identifier)
        for budget in (50,300,500,2200):
            text=documents.prompt_block(self.store,self.project,'amber',budget)
            self.assertLessEqual(len(text.encode('utf-8')),budget)
            if text:
                self.assertIn('sha256',text);self.assertTrue(text.endswith('[End source]\n'))

    def test_chat_context_uses_only_selected_project_documents(self):
        identifier=self.attachment();documents.index(self.store,self.project,identifier)
        self.assertIn(documents.digest('Amber deployment rule: keep the demo service private.'),server.conversation_project_context(self.project,'amber'))
        self.assertNotIn('Selected project document search',server.conversation_project_context(self.other,'amber'))


class DocumentApiTests(unittest.TestCase):
    setUp=DocumentTests.setUp
    restore=DocumentTests.restore
    attachment=DocumentTests.attachment
    def test_owner_confirmation_and_foreign_reference_controls(self):
        http=server.runtime.ControlServer(('127.0.0.1',0),server.App);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def request(path,body=None,token='synthetic-documents-owner-00000000000'):
            c=HTTPConnection('127.0.0.1',http.server_port,timeout=5)
            try:
                headers={'Content-Type':'application/json'}
                if token:headers['Authorization']='Bearer '+token
                c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
                r=c.getresponse();return r.status,json.load(r)
            finally:c.close()
        try:
            identifier=self.attachment();foreign=self.attachment(project=self.other);path=f'/api/projects/{self.project}/documents'
            self.assertEqual(request(path,token='')[0],401)
            with patch.object(server,'WORKER_AUTH',security.OwnerAuth('synthetic-documents-worker-000000000')):
                self.assertEqual(request(path,token='synthetic-documents-worker-000000000')[0],403)
            self.assertEqual(request(path+'/index',{'attachment_id':identifier,'confirm':1})[0],400)
            self.assertEqual(request(path+'/index',{'attachment_id':foreign,'confirm':True})[0],404)
            self.assertEqual(request(path+'/index',{'attachment_id':identifier,'confirm':True})[0],200)
            code,body=request(path+'/search?q=amber');self.assertEqual(code,200);self.assertEqual(body['hits'][0]['attachment_id'],identifier)
            self.assertEqual(request(path+'/remove',{'attachment_id':identifier,'confirm':True})[0],200)
            self.assertEqual(request(path+'/search?q=amber')[1]['hits'],[])
        finally:http.shutdown();http.server_close();thread.join(timeout=3)


if __name__=='__main__':unittest.main()
