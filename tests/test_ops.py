import json
import sqlite3
import time
from scripts.ops import backup,ledger,private_json,restore,retention,import_roster
from .conftest import register


def test_backup_restore_applies_withdrawals(client,app,config,tmp_path):
    d,h=register(client)
    path=backup(app.state.store,tmp_path/'backups')
    assert path.exists()
    assert client.delete('/api/sessions/me',headers=h).status_code==200
    log=tmp_path/'deletions.json';private_json(log,ledger(app.state.store))
    # Client is idle and holds no SQLite connections; this unit test is offline restore.
    restore(config,path,log,replace=True,service_stopped=True)
    with sqlite3.connect(config.db_path) as c:
        assert c.execute('SELECT count(*) FROM participants').fetchone()[0]==0


def test_restore_refuses_without_offline_flag(client,app,config,tmp_path):
    import pytest
    path=backup(app.state.store,tmp_path/'backups');log=tmp_path/'ledger.json';private_json(log,ledger(app.state.store))
    with pytest.raises(ValueError):restore(config,path,log,replace=True,service_stopped=False)


def test_retention_dry_run_then_apply(client,app,config):
    d,h=register(client)
    with app.state.store.connect() as c:
        c.execute('UPDATE participants SET created_at=? WHERE id=?',(int(time.time())-8*86400,d['id']))
    assert retention(app.state.store,False)==1
    assert client.get('/api/sessions/me',headers=h).status_code==200
    assert retention(app.state.store,True)==1
    assert client.get('/api/sessions/me',headers=h).status_code==401
    assert d['id'] in ledger(app.state.store)['record_ids']


def test_roster_import_dry_run(client,app,tmp_path):
    f=tmp_path/'roster.csv';f.write_text('student_id,name\n00009999,名册测试\n',encoding='utf-8')
    import_roster(app.state.store,f,False)
    with app.state.store.connect() as c:assert c.execute('SELECT count(*) FROM roster').fetchone()[0]==0
    import_roster(app.state.store,f,True)
    with app.state.store.connect() as c:assert c.execute('SELECT count(*) FROM roster').fetchone()[0]==1
def test_safe_default_journal(client,app):
    with app.state.store.connect() as c:
        assert c.execute('PRAGMA journal_mode').fetchone()[0]=='delete'


def test_wal_runtime_gate():
    from backend.store import wal_runtime_fixed
    for v in [(3,46,1),(3,51,2),(3,50,6),(3,44,5)]:assert not wal_runtime_fixed(v)
    for v in [(3,51,3),(3,53,0),(3,50,7),(3,44,6)]:assert wal_runtime_fixed(v)


def test_existing_journal_not_silently_changed(config):
    from backend.store import Store
    import pytest
    config.db_path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(config.db_path) as c:
        c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE migration_test(x)')
    with pytest.raises(RuntimeError,match='offline migration'):Store(config)

def test_newer_schema_is_not_silently_downgraded(config):
    from backend.store import Store
    import pytest
    with sqlite3.connect(config.db_path) as c:c.execute('PRAGMA user_version=2')
    with pytest.raises(RuntimeError,match='schema version'):Store(config)
    with sqlite3.connect(config.db_path) as c:assert c.execute('PRAGMA user_version').fetchone()[0]==2
