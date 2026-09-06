-- Schema v1; no student data.
CREATE INDEX participant_time ON participants(created_at);

CREATE TABLE admin_sessions(token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);

CREATE TABLE audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, record_id TEXT NOT NULL);

CREATE TABLE participants(
              id TEXT PRIMARY KEY, cohort TEXT NOT NULL, sid_key TEXT NOT NULL,
              identity_enc TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
              privacy_version TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
              submitted_at INTEGER, status TEXT NOT NULL DEFAULT 'draft', revision INTEGER NOT NULL DEFAULT 0,
              answers_enc TEXT NOT NULL, result_enc TEXT, review_enc TEXT, receipt TEXT,
              UNIQUE(cohort,sid_key)
            );

CREATE TABLE rate_limits(key TEXT PRIMARY KEY, window_start INTEGER NOT NULL, count INTEGER NOT NULL);

CREATE TABLE roster(cohort TEXT NOT NULL, sid_key TEXT NOT NULL, name_key TEXT NOT NULL, PRIMARY KEY(cohort,sid_key));

CREATE TABLE sqlite_sequence(name,seq);
