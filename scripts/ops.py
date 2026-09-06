#!/usr/bin/env python3
"""Backups, retention, roster import and explicitly offline restore."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,re,sqlite3,sys,time,unicodedata,uuid
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.settings import Settings
from backend.store import Store
from backend.security import keyed_hash

DELETE_ACTIONS=('participant_withdraw','delete','retention_delete')
def ledger(store):
    with store.connect() as c:
        rows=c.execute("SELECT DISTINCT record_id FROM audit WHERE action IN ('participant_withdraw','delete','retention_delete')").fetchall()
    return {'generated_at':int(time.time()),'record_ids':[r[0] for r in rows if r[0]]}

def private_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=path.with_name(path.name+'.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
    os.replace(tmp,path)

def backup(store,out):
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    target=out/('campus-backup-'+stamp+'-'+uuid.uuid4().hex[:6]+'.sqlite3')
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    with store.connect() as src,closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity check failed')
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    private_json(target.with_suffix('.json'),{'file':target.name,'sha256':digest,'created_at':int(time.time()),'schema_version':1,'index_key_fingerprint':hashlib.sha256(store.settings.hmac_key.encode()).hexdigest()[:16]})
    private_json(out/'deletions-latest.json',ledger(store))
    cutoff=time.time()-30*86400
    for old in out.glob('campus-backup-*.sqlite3'):
        if old.stat().st_mtime<cutoff:
            old.unlink();old.with_suffix('.json').unlink(missing_ok=True)
    print(json.dumps({'backup':str(target),'sha256':digest,'integrity':'ok'}))
    return target

def retention(store,apply=False):
    now=int(time.time());cfg=store.settings
    with store.connect() as c:
        rows=c.execute("SELECT id FROM participants WHERE (status='submitted' AND submitted_at<?) OR (status='draft' AND created_at<?)",(now-cfg.retention_days*86400,now-cfg.draft_days*86400)).fetchall()
        if apply:
            for row in rows:
                c.execute('DELETE FROM participants WHERE id=?',(row['id'],))
                c.execute('INSERT INTO audit(at,actor,action,record_id) VALUES(?,?,?,?)',(now,'scheduler','retention_delete',row['id']))
            c.execute('DELETE FROM admin_sessions WHERE expires_at<?',(now,))
            c.execute('DELETE FROM rate_limits WHERE window_start<?',(now-3600,))
            c.execute('DELETE FROM audit WHERE at<?',(now-max(cfg.retention_days,31)*86400,))
    print(json.dumps({'expired_records':len(rows),'applied':apply}))
    return len(rows)

def import_roster(store,path,apply=False):
    cfg=store.settings;values=[];seen=set()
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not {'student_id','name'}<=set(reader.fieldnames or []):raise ValueError('Required CSV headers: student_id,name')
        for line,row in enumerate(reader,2):
            sid=unicodedata.normalize('NFKC',row['student_id']).strip();name=unicodedata.normalize('NFKC',row['name']).strip()
            if not re.fullmatch(cfg.student_id_pattern,sid) or not 2<=len(name)<=40:raise ValueError('Invalid roster fields at line '+str(line))
            if sid in seen:raise ValueError('Repeated student_id at line '+str(line))
            seen.add(sid);values.append((cfg.cohort,keyed_hash(cfg.hmac_key,'sid:'+cfg.cohort,sid),keyed_hash(cfg.hmac_key,'name',name)))
    if apply:
        with store.connect() as c:c.executemany('INSERT INTO roster VALUES(?,?,?) ON CONFLICT(cohort,sid_key) DO UPDATE SET name_key=excluded.name_key',values)
        store.audit('import_roster',actor='operator')
    print(json.dumps({'valid_rows':len(values),'applied':apply}))

def restore(cfg,source,deletion_ledger,replace=False,service_stopped=False):
    if not service_stopped:raise ValueError('Stop the service first, then pass --service-stopped')
    if not source.is_file() or source.resolve()==cfg.db_path.resolve():raise ValueError('Invalid backup path')
    metadata=json.loads(source.with_suffix('.json').read_text('utf-8'))
    if hashlib.sha256(source.read_bytes()).hexdigest()!=metadata['sha256']:raise ValueError('Backup checksum mismatch')
    if metadata.get('index_key_fingerprint')!=hashlib.sha256(cfg.hmac_key.encode()).hexdigest()[:16]:raise ValueError('Index key differs; do not rotate data keys during restore')
    log=json.loads(deletion_ledger.read_text('utf-8'))
    ids=log.get('record_ids')
    if not isinstance(ids,list) or 'generated_at' not in log:raise ValueError('A current deletion ledger is mandatory')
    for value in ids:uuid.UUID(value)
    if cfg.db_path.exists() and not replace:raise ValueError('Target exists. Explicit --replace is required')
    cfg.db_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=cfg.db_path.with_name('.restore-'+uuid.uuid4().hex+'.sqlite3')
    try:
        with closing(sqlite3.connect(source)) as src,closing(sqlite3.connect(temporary)) as dest:
            src.backup(dest)
            if dest.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Backup is corrupt')
            from cryptography.fernet import Fernet
            row=dest.execute('SELECT identity_enc FROM participants LIMIT 1').fetchone()
            if row:Fernet(cfg.encryption_key.encode()).decrypt(row[0].encode())
            dest.executemany('DELETE FROM participants WHERE id=?',[(x,) for x in ids])
            dest.execute('DELETE FROM admin_sessions')
            dest.commit()
            dest.execute('PRAGMA journal_mode=DELETE')
        if cfg.db_path.exists():
            previous=cfg.db_path.with_name('before-restore-'+str(int(time.time()))+'.sqlite3')
            with closing(sqlite3.connect(cfg.db_path)) as src,closing(sqlite3.connect(previous)) as dst:
                checkpoint=src.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
                if checkpoint[0]:raise ValueError('Database remains busy; stop all writers')
                src.backup(dst)
            if os.name=='posix':os.chmod(previous,0o600)
        for suffix in ['-wal','-shm']:
            Path(str(cfg.db_path)+suffix).unlink(missing_ok=True)
        if os.name=='posix':os.chmod(temporary,0o600)
        os.replace(temporary,cfg.db_path)
    finally:temporary.unlink(missing_ok=True)
    print(json.dumps({'restored':True,'deletions_reapplied':len(ids),'admin_sessions_cleared':True}))

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('backup');b.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('retention');r.add_argument('--apply',action='store_true')
    i=sub.add_parser('import-roster');i.add_argument('--file',type=Path,required=True);i.add_argument('--apply',action='store_true')
    l=sub.add_parser('export-deletions');l.add_argument('--output',type=Path,required=True)
    c=sub.add_parser('clear-roster');c.add_argument('--apply',action='store_true')
    t=sub.add_parser('restore');t.add_argument('--backup',type=Path,required=True);t.add_argument('--ledger',type=Path,required=True);t.add_argument('--replace',action='store_true');t.add_argument('--service-stopped',action='store_true')
    a=p.parse_args();cfg=Settings.from_env()
    if a.command=='restore':return restore(cfg,a.backup,a.ledger,a.replace,a.service_stopped)
    store=Store(cfg)
    if a.command=='backup':backup(store,a.output)
    elif a.command=='retention':retention(store,a.apply)
    elif a.command=='import-roster':import_roster(store,a.file,a.apply)
    elif a.command=='export-deletions':private_json(a.output,ledger(store));print('Deletion ledger exported privately.')
    elif a.command=='clear-roster':
        with store.connect() as c:
            count=c.execute('SELECT count(*) FROM roster WHERE cohort=?',(cfg.cohort,)).fetchone()[0]
            if a.apply:c.execute('DELETE FROM roster WHERE cohort=?',(cfg.cohort,))
        print(json.dumps({'roster_rows':count,'applied':a.apply}))
if __name__=='__main__':
    try:main()
    except Exception as e:raise SystemExit('STOP: '+str(e))