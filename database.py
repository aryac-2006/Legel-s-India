"""SQLite data layer (standard library). All user-owned tables carry user_id and every
id-based lookup in the app goes through owned() so ownership is enforced server-side."""
import sqlite3
from contextlib import contextmanager
import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','professional','admin')),
  is_active INTEGER NOT NULL DEFAULT 1, language TEXT NOT NULL DEFAULT 'English',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS login_attempts(id INTEGER PRIMARY KEY, email TEXT, ok INTEGER, ts REAL);
CREATE INDEX IF NOT EXISTS ix_login_email ON login_attempts(email, ts);

CREATE TABLE IF NOT EXISTS legal_sources(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, act TEXT NOT NULL, section TEXT NOT NULL DEFAULT '',
  domain TEXT NOT NULL, doc_type TEXT NOT NULL DEFAULT 'Statute', source_name TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '', text TEXT NOT NULL,
  verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK(verification_status IN ('unverified','verified','outdated')),
  version TEXT NOT NULL DEFAULT '1', retrieved_on TEXT, effective_info TEXT DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(act, section, version));
CREATE INDEX IF NOT EXISTS ix_src_domain ON legal_sources(domain);
CREATE TABLE IF NOT EXISTS source_versions(
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES legal_sources(id) ON DELETE CASCADE,
  version TEXT, text TEXT, verification_status TEXT, note TEXT, changed_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS legal_chunks(
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES legal_sources(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL, text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_chunk_src ON legal_chunks(source_id);

CREATE TABLE IF NOT EXISTS conversations(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, language TEXT DEFAULT 'English', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_conv_user ON conversations(user_id);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
  payload TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS retrieved_sources(
  id INTEGER PRIMARY KEY, message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  source_id INTEGER NOT NULL REFERENCES legal_sources(id) ON DELETE CASCADE, chunk_id INTEGER,
  rank INTEGER, score REAL, cited INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS answer_feedback(
  id INTEGER PRIMARY KEY, message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, note TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename TEXT NOT NULL, stored_path TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
  doc_type TEXT DEFAULT 'general', text TEXT DEFAULT '', pages TEXT DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'uploaded', status_note TEXT DEFAULT '', summary TEXT DEFAULT '',
  entities TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_doc_user ON documents(user_id);
CREATE TABLE IF NOT EXISTS findings(
  id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  kind TEXT NOT NULL DEFAULT 'clause', category TEXT NOT NULL, passage TEXT DEFAULT '',
  explanation TEXT DEFAULT '', page INTEGER, reason TEXT DEFAULT '', priority TEXT DEFAULT 'Low',
  verification TEXT DEFAULT 'Rule-based extraction - not legally verified',
  review_status TEXT NOT NULL DEFAULT 'Unreviewed', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_find_doc ON findings(document_id);
CREATE TABLE IF NOT EXISTS comparisons(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  doc_a TEXT, doc_b TEXT, result TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS matters(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, category TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open',
  description TEXT DEFAULT '', is_demo INTEGER DEFAULT 0, archived INTEGER DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_matter_user ON matters(user_id);
CREATE TABLE IF NOT EXISTS matter_notes(
  id INTEGER PRIMARY KEY, matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, body TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS matter_links(
  id INTEGER PRIMARY KEY, matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, ref_id INTEGER NOT NULL, label TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(matter_id, kind, ref_id));
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  matter_id INTEGER REFERENCES matters(id) ON DELETE SET NULL, title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'task' CHECK(kind IN ('task','deadline','event')),
  description TEXT DEFAULT '', due_date TEXT NOT NULL, reminder_days INTEGER DEFAULT 1,
  done INTEGER DEFAULT 0, is_demo INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_task_user_due ON tasks(user_id, due_date);
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE, title TEXT NOT NULL,
  description TEXT DEFAULT '', event_date TEXT, added_on TEXT DEFAULT CURRENT_TIMESTAMP,
  file_type TEXT DEFAULT '', filename TEXT DEFAULT '', notes TEXT DEFAULT '',
  timeline_note TEXT DEFAULT '', sha256 TEXT DEFAULT '');

CREATE TABLE IF NOT EXISTS drafts(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  matter_id INTEGER REFERENCES matters(id) ON DELETE SET NULL, template TEXT NOT NULL, title TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS draft_versions(
  id INTEGER PRIMARY KEY, draft_id INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
  version INTEGER NOT NULL, content TEXT NOT NULL, fields TEXT DEFAULT '{}', note TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(draft_id, version));

CREATE TABLE IF NOT EXISTS collections(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, name));
CREATE TABLE IF NOT EXISTS saved_research(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source_id INTEGER NOT NULL REFERENCES legal_sources(id) ON DELETE CASCADE,
  collection_id INTEGER REFERENCES collections(id) ON DELETE SET NULL, note TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, source_id));
CREATE TABLE IF NOT EXISTS saved_searches(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  query TEXT NOT NULL, filters TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS help_prep(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  matter_id INTEGER REFERENCES matters(id) ON DELETE SET NULL, title TEXT, answers TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS audit_events(
  id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  action TEXT NOT NULL, detail TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_audit_user ON audit_events(user_id);
CREATE TABLE IF NOT EXISTS ingestion_jobs(
  id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, filename TEXT,
  status TEXT, rows_ok INTEGER DEFAULT 0, rows_failed INTEGER DEFAULT 0, error TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS error_log(
  id INTEGER PRIMARY KEY, location TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

OWNED_TABLES = {"matters", "documents", "drafts", "conversations", "tasks", "evidence",
                "comparisons", "help_prep", "collections", "saved_searches", "saved_research",
                "matter_notes", "matter_links"}


def _connect():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = _connect()
    try:
        yield conn
        conn.commit()          # one transaction per block; rolled back on error
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as c:
        c.executescript(SCHEMA)


def q(sql, params=()):
    with db() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def one(sql, params=()):
    rows = q(sql, params)
    return rows[0] if rows else None


def ex(sql, params=()):
    with db() as c:
        return c.execute(sql, params).lastrowid


def owned(table, row_id, user_id):
    """Fetch a row only if it belongs to user_id. Returns None otherwise (no existence leak)."""
    if table not in OWNED_TABLES:
        raise ValueError("table not ownership-checked")
    return one(f"SELECT * FROM {table} WHERE id=? AND user_id=?", (row_id, user_id))


def audit(user_id, action, detail=""):
    ex("INSERT INTO audit_events(user_id,action,detail) VALUES(?,?,?)", (user_id, action, str(detail)[:255]))


def log_error(location, exc):
    try:
        ex("INSERT INTO error_log(location,message) VALUES(?,?)", (location, f"{type(exc).__name__}: {exc}"[:500]))
    except Exception:
        pass
