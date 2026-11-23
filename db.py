"""SQLite storage for the price tracker.

Two tables:
  products(product_key PK, name, store, product_url)
  price_history(id, product_key, name, store, checked_at, price, mrp, source)

UNIQUE(product_key, checked_at, source) makes every ingest idempotent:
re-running a fetch over the same minute inserts nothing new.
Unknown prices are stored as NULL - never invented.
"""
import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("PT_DB", os.path.join(BASE, "prices.sqlite"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    store TEXT,
    product_url TEXT
);
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_key TEXT NOT NULL,
    name TEXT,
    store TEXT,
    checked_at TEXT NOT NULL,
    price REAL,
    mrp REAL,
    source TEXT NOT NULL,
    UNIQUE(product_key, checked_at, source)
);
CREATE INDEX IF NOT EXISTS idx_ph_key_time ON price_history(product_key, checked_at);
CREATE INDEX IF NOT EXISTS idx_ph_time ON price_history(checked_at);
"""


def get_db():
    # timeout=120: if two fetchers share a schedule slot, the second waits
    # politely for the write lock instead of failing on contention.
    conn = sqlite3.connect(DB_PATH, timeout=120)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def upsert_product(conn, key, name, store=None, url=None):
    conn.execute(
        "INSERT INTO products(product_key, name, store, product_url)"
        " VALUES(?,?,?,?)"
        " ON CONFLICT(product_key) DO UPDATE SET"
        " name=excluded.name,"
        " store=COALESCE(excluded.store, products.store),"
        " product_url=COALESCE(excluded.product_url, products.product_url)",
        (key, name, store, url))


def add_point(conn, key, name, store, checked_at, price, mrp, source):
    """Insert one history point. Returns 1 if new, 0 if duplicate."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO price_history"
        "(product_key, name, store, checked_at, price, mrp, source)"
        " VALUES(?,?,?,?,?,?,?)",
        (key, name, store, checked_at, price, mrp, source))
    return cur.rowcount
