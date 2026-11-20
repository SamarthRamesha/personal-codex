#!/usr/bin/env python3
"""Independent synthetic lexical-retrieval checks; no files, model or network input."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import documents


class FixtureStore:
    def __init__(self):
        self.conn=sqlite3.connect(':memory:');self.conn.row_factory=sqlite3.Row;self.lock=threading.RLock()
        self.conn.execute('CREATE TABLE project_attachments (id TEXT PRIMARY KEY,project_id TEXT,name TEXT,mechanism TEXT,excerpt TEXT)')
        documents.initialize(self.conn)
    def rows(self,sql,args=()):return [dict(row) for row in self.conn.execute(sql,args)]
    def one(self,sql,args=()):
        row=self.conn.execute(sql,args).fetchone();return dict(row) if row else None


def evaluate():
    store=FixtureStore()
    corpus={
        'architecture':'Orchid job runner binds its local control socket to loopback port 7421. The queue uses ordered job identifiers.',
        'cancellation':'Cancellation waits for ordered acknowledgements. A cancelled operation is not replayed automatically after restart.',
        'inference':'Qwen inference uses an explicitly chosen local model with a configured context window. Token throughput is reported by the provider.',
        'training':'Stratified validation separates held-out test observations. Fairness reports subgroup denominators. Preprocessing is fitted inside cross-validation.',
        'recovery':'Encrypted snapshots preserve SQLite state. Retention is operator reviewed. Restore targets a new destination and checks integrity.',
        'frontend':'The accessible interface has keyboard labels and a responsive layout. The results panel displays model comparisons.',
    }
    try:
        for name,text in corpus.items():
            store.conn.execute('INSERT INTO project_attachments VALUES (?,?,?,?,?)',(name,'chosen',name+'.md','synthetic text',text))
            documents.index(store,'chosen',name)
        store.conn.execute('INSERT INTO project_attachments VALUES (?,?,?,?,?)',('foreign','other','private-other.md','synthetic text','Obsidian foreign-project exclusive reference.'))
        store.conn.commit();documents.index(store,'other','foreign')
        cases=[('runner loopback port','architecture'),('cancelled ordered acknowledgements','cancellation'),
               ('Qwen inference context','inference'),('stratified validation fairness','training'),
               ('encrypted snapshots retention','recovery'),('accessible keyboard responsive','frontend')]
        results=[]
        for query,expected in cases:
            hits=documents.search(store,'chosen',query,5);ids=[hit['attachment_id'] for hit in hits]
            for hit in hits:assert hit['source_hash']==hashlib.sha256(corpus[hit['attachment_id']].encode()).hexdigest()
            results.append({'query':query,'expected':expected,'retrieved':ids,'reciprocal_rank':1/(ids.index(expected)+1) if expected in ids else 0})
        assert all(row['reciprocal_rank']==1 for row in results),results
        assert not documents.search(store,'chosen','Obsidian')
        assert not documents.search(store,'chosen','unicorn astrophysics')
        store.conn.execute("UPDATE project_attachments SET excerpt='Changed source awaiting explicit reindex' WHERE id='inference'");store.conn.commit()
        assert not documents.search(store,'chosen','Qwen')
        documents.remove(store,'chosen','architecture');assert not documents.search(store,'chosen','loopback')
        return {'success':True,'scope':'synthetic lexical retrieval, not semantic retrieval or model-quality measurement',
                'sqlite_version':sqlite3.sqlite_version,'queries':results,'precision_at_1':1.0,'mean_reciprocal_rank':1.0,
                'foreign_project_excluded':True,'unmatched_query_empty':True,'stale_source_excluded':True,'removed_source_excluded':True,
                'model_calls':0,'source_files_scanned':0}
    finally:store.conn.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():parser.error('Use a new output path; previous evidence is preserved')
    result=evaluate()
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({key:value for key,value in result.items() if key!='queries'}))


if __name__=='__main__':main()
