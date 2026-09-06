from __future__ import annotations
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from cryptography.fernet import Fernet
from .settings import Settings

def wal_runtime_fixed(version: tuple[int, ...]) -> bool:
    """SQLite WAL-reset fix released 2026-03-13; exact earlier fixed branches only."""
    v=tuple(version[:3])
    return v >= (3,51,3) or ((3,50,7) <= v < (3,51,0)) or ((3,44,6) <= v < (3,45,0))
class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.path = settings.db_path
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.cipher = Fernet(settings.encryption_key.encode())
        existing = self.path.exists() and self.path.stat().st_size > 0
        if settings.journal_mode == 'WAL' and not wal_runtime_fixed(sqlite3.sqlite_version_info):
            raise RuntimeError('WAL requires SQLite 3.51.3+ or known fixed backport 3.50.7/3.44.6. Use DELETE for a new database.')
        with self.connect() as conn:
            current = conn.execute('PRAGMA journal_mode').fetchone()[0].upper()
            if existing and current != settings.journal_mode:
                raise RuntimeError('Journal mode differs from existing DB. Stop all writers and review an offline migration; do not change modes during service startup.')
            schema = conn.execute('PRAGMA user_version').fetchone()[0]
            if schema not in (0,1):
                raise RuntimeError('Unsupported schema version; use an explicit reviewed migration')
            conn.execute('PRAGMA journal_mode='+settings.journal_mode)
            conn.executescript('''
            CREATE TABLE IF NOT EXISTS participants(
              id TEXT PRIMARY KEY, cohort TEXT NOT NULL, sid_key TEXT NOT NULL,
              identity_enc TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
              privacy_version TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
              submitted_at INTEGER, status TEXT NOT NULL DEFAULT 'draft', revision INTEGER NOT NULL DEFAULT 0,
              answers_enc TEXT NOT NULL, result_enc TEXT, review_enc TEXT, receipt TEXT,
              UNIQUE(cohort,sid_key)
            );
            CREATE TABLE IF NOT EXISTS admin_sessions(token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS rate_limits(key TEXT PRIMARY KEY, window_start INTEGER NOT NULL, count INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, record_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS roster(cohort TEXT NOT NULL, sid_key TEXT NOT NULL, name_key TEXT NOT NULL, PRIMARY KEY(cohort,sid_key));
            CREATE INDEX IF NOT EXISTS participant_time ON participants(created_at);
            PRAGMA user_version=1;
            ''')
        if os.name == 'posix':
            os.chmod(self.path,0o600)

    @contextmanager
    def connect(self):
        conn=sqlite3.connect(str(self.path),timeout=15)
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=15000')
        conn.execute('PRAGMA synchronous=FULL')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally: conn.close()

    def seal(self, value: object) -> str:
        return self.cipher.encrypt(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()).decode()

    def open(self, value: str | None):
        return json.loads(self.cipher.decrypt(value.encode())) if value else None

    def audit(self, action: str, record: str='', actor: str='admin'):
        with self.connect() as c:
            c.execute('INSERT INTO audit(at,actor,action,record_id) VALUES(?,?,?,?)',(int(time.time()),actor,action,record))

    def limit(self, key: str, maximum: int, seconds: int) -> bool:
        now=int(time.time())
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('DELETE FROM rate_limits WHERE window_start < ?', (now-3600,))
            row=c.execute('SELECT * FROM rate_limits WHERE key=?',(key,)).fetchone()
            if row is None or row['window_start']+seconds <= now:
                c.execute('INSERT OR REPLACE INTO rate_limits VALUES(?,?,?)',(key,now,1)); return True
            if row['count'] >= maximum: return False
            c.execute('UPDATE rate_limits SET count=count+1 WHERE key=?',(key,)); return True
