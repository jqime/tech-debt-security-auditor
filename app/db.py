import os
import sqlite3
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "")
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "dashboard.db"

USE_PG = bool(DATABASE_URL)


class Database:
    def __init__(self):
        self.conn = None
        self._pg = USE_PG

    def connect(self):
        if self._pg:
            import psycopg2
            import psycopg2.extras
            self.conn = psycopg2.connect(DATABASE_URL)
            self.conn.autocommit = False
            return self.conn
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        return self.conn

    def execute(self, sql, params=None):
        if self._pg:
            import psycopg2.extras
            cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params or ())
            return cur
        return self.conn.execute(sql, params or ())

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def get_db():
    db = Database()
    db.connect()
    return db


def init_db():
    db = get_db()
    sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            repo_url TEXT NOT NULL,
            customer_email TEXT DEFAULT '',
            plan_type TEXT DEFAULT 'auditoria_unica',
            status TEXT DEFAULT 'pending',
            audit_dir TEXT DEFAULT '',
            demo_id TEXT DEFAULT '',
            error TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            started_at TEXT,
            finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            email TEXT,
            empresa TEXT,
            repo_url TEXT,
            mensaje TEXT,
            converted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            stripe_session_id TEXT,
            amount INTEGER,
            currency TEXT DEFAULT 'eur',
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS compliance_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            repo_url TEXT,
            secrets_score REAL,
            vulnerabilities_score REAL,
            complexity_score REAL,
            duplication_score REAL,
            perimeter_score REAL,
            overall_score REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS whitelabel_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT UNIQUE NOT NULL,
            subdomain TEXT UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            primary_color TEXT DEFAULT '#6366f1',
            logo_url TEXT DEFAULT '',
            custom_domain TEXT DEFAULT '',
            plan_type TEXT DEFAULT 'enterprise',
            features_json TEXT DEFAULT '{}',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """
    if USE_PG:
        pg_sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        pg_sql = pg_sql.replace("datetime('now')", "NOW()")
        for stmt in pg_sql.split(";"):
            s = stmt.strip()
            if s and s.upper().startswith("CREATE"):
                try:
                    db.execute(s + ";")
                    db.commit()
                except Exception:
                    db.conn.rollback()
    else:
        db.execute(sql)
        db.commit()
    db.close()
