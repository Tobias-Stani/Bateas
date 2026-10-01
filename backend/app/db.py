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
