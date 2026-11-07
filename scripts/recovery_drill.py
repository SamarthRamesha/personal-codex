#!/usr/bin/env python3
"""Synthetic local disaster-recovery drill. Never accepts a personal source directory."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import recovery,server,secure_files


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--scratch-parent',type=Path,required=True);a=p.parse_args()
    from cryptography.fernet import Fernet
    with tempfile.TemporaryDirectory(prefix='recovery-drill-',dir=a.scratch_parent) as directory:
        base=Path(directory).resolve();data=base/'data';data.mkdir(mode=0o700)
        with patch.object(server,'DATA',data),patch.object(server,'DB_PATH',data/'personal_codex.db'):store=server.Store()
        project=data/'projects'/'synthetic';project.mkdir(parents=True);(project/'example.py').write_text('def value(): return 42\n')
        for command in (['git','init','--quiet'],['git','config','user.name','Synthetic'],['git','config','user.email','synthetic@example.invalid'],['git','add','.'],['git','commit','--quiet','-m','synthetic recoverable commit']):subprocess.run(command,cwd=project,check=True,capture_output=True)
        store.write('INSERT INTO projects VALUES (?,?,?,?)',('project','Synthetic',str(project),1))
        store.write('INSERT INTO conversations (id,title,created_at,updated_at) VALUES (?,?,?,?)',('before','included at checkpoint',1,1))
        store.conn.close()
        release=base/'release.zip'
        import zipfile
        with zipfile.ZipFile(release,'w') as z:z.writestr('personal-codex/README.md','synthetic source release')
        key=base/'key';secure_files.write_new(key,Fernet.generate_key())
        bundle=base/'encrypted.pcr'
        with patch.dict(os.environ,{'PERSONAL_CODEX_RESERVE_GB':'1'}):
            checkpoint=recovery.checkpoint(data,bundle,key,release,{'PC_ORIGIN':'https://synthetic.private.ts.net'})
            db=sqlite3.connect(data/'personal_codex.db');db.execute('INSERT INTO conversations (id,title,created_at,updated_at) VALUES (?,?,?,?)',('after','not included after checkpoint',2,2));db.commit();db.close()
            restored=recovery.restore(bundle,base/'new-root',key)
        db=sqlite3.connect(base/'new-root/data/personal_codex.db')
        try:titles=[row[0] for row in db.execute('SELECT title FROM conversations')];path=db.execute('SELECT path FROM projects').fetchone()[0]
        finally:db.close()
        source_db=sqlite3.connect(data/'personal_codex.db')
        try:source_preserved=source_db.execute("SELECT COUNT(*) FROM conversations WHERE id='after'").fetchone()[0]==1
        finally:source_db.close()
        recovered_commit=subprocess.check_output(['git','-C',path,'log','-1','--format=%s'],text=True).strip()
        report={'synthetic':True,'tested_on_jarvis':False,'checkpoint':checkpoint,'restore':restored,
                'checks':{'checkpoint_record_present':'included at checkpoint' in titles,'later_record_absent':'not included after checkpoint' not in titles,
                          'project_file_restored':(Path(path)/'example.py').read_text()=='def value(): return 42\n','git_history_restored':recovered_commit=='synthetic recoverable commit',
                          'execution_lock_present':(base/'new-root/data/RECOVERY_LOCKED.json').exists(),'original_later_record_preserved':source_preserved},
                'rpo':'Latest completed offline checkpoint only; post-checkpoint records are not restored',
                'rto_limitations':'Measured tiny warm local fixture only. JARVIS storage/image/credential/Git-repair/approval recovery time is unmeasured.',
                'credentials':'No production credentials or private keys collected; synthetic encryption key destroyed with this disposable fixture',
                'automatic_retention':'none; only this explicitly disposable synthetic fixture is cleaned up'}
        if not all(report['checks'].values()):raise ValueError('Synthetic recovery drill failed')
        secure_files.write_new(a.evidence,json.dumps(report,indent=2).encode())
        print(json.dumps({'passed':len(report['checks']),'checkpoint_ms':checkpoint['elapsed_ms'],'restore_ms':restored['elapsed_ms'],'tested_on_jarvis':False}))

if __name__=='__main__':main()
