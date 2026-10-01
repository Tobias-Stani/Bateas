"""Conexiones SQLite: el registro de disquerías y la base propia de cada una (aislamiento por archivo)."""
import sqlite3
from datetime import datetime, timezone

from .config import REGISTRY
from .storage import db_path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


# --- registro de disquerías ---

def registry():
    return connect(REGISTRY)


def init_registry():
    with registry() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS tenants (
            slug TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
            admin_hash TEXT NOT NULL, logo TEXT, accent TEXT, highlight TEXT, notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, status_at TEXT NOT NULL)""")
        # registro central (services/audit.py): no depende de ninguna disquería, así que sobrevive a que se elimine una
        con.execute("""CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at TEXT NOT NULL, slug TEXT NOT NULL,
            actor TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL)""")
        con.execute("CREATE INDEX IF NOT EXISTS events_slug ON events (slug, id)")
        con.execute("""CREATE TABLE IF NOT EXISTS payments (payment_id TEXT PRIMARY KEY, slug TEXT NOT NULL, order_id INTEGER NOT NULL,
            status TEXT NOT NULL, total REAL NOT NULL, fee REAL NOT NULL, mp_fee REAL, net REAL, payer TEXT, items TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    con.close()


# --- base de cada disquería ---

def db(t):
    return connect(db_path(t["slug"]))


def get_setting(t, key, default=None):
    con = db(t)
    con.execute("CREATE TABLE IF NOT EXISTS settings (key PRIMARY KEY, value)")
    row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    con.close()
    return row[0] if row else default


def set_settings(t, **values):
    con = db(t)
    with con:
        con.execute("CREATE TABLE IF NOT EXISTS settings (key PRIMARY KEY, value)")
        con.executemany("INSERT OR REPLACE INTO settings VALUES (?, ?)", values.items())
    con.close()
