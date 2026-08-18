import sqlite3
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    sku_id TEXT PRIMARY KEY,
    product_id TEXT,
    display_name TEXT,
    brand TEXT,
    url TEXT,
    first_seen_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT NOT NULL,
    price_type TEXT NOT NULL,
    price INTEGER NOT NULL,
    search_term TEXT,
    observed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (sku_id) REFERENCES products(sku_id)
);

CREATE INDEX IF NOT EXISTS idx_price_obs_sku_type
    ON price_observations (sku_id, price_type, observed_at);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT NOT NULL,
    price_type TEXT NOT NULL,
    new_price INTEGER NOT NULL,
    reference_price REAL NOT NULL,
    reason TEXT NOT NULL,
    notified INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def upsert_product(conn, sku_id, product_id, display_name, brand, url):
    conn.execute(
        """
        INSERT INTO products (sku_id, product_id, display_name, brand, url, last_seen_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(sku_id) DO UPDATE SET
            product_id=excluded.product_id,
            display_name=excluded.display_name,
            brand=excluded.brand,
            url=excluded.url,
            last_seen_at=datetime('now')
        """,
        (sku_id, product_id, display_name, brand, url),
    )


def get_price_history(conn, sku_id, price_type, limit=20):
    rows = conn.execute(
        """
        SELECT price FROM price_observations
        WHERE sku_id = ? AND price_type = ?
        ORDER BY observed_at DESC
        LIMIT ?
        """,
        (sku_id, price_type, limit),
    ).fetchall()
    return [row["price"] for row in rows]


def insert_observation(conn, sku_id, price_type, price, search_term):
    conn.execute(
        """
        INSERT INTO price_observations (sku_id, price_type, price, search_term)
        VALUES (?, ?, ?, ?)
        """,
        (sku_id, price_type, price, search_term),
    )


def insert_alert(conn, sku_id, price_type, new_price, reference_price, reason):
    conn.execute(
        """
        INSERT INTO alerts (sku_id, price_type, new_price, reference_price, reason)
        VALUES (?, ?, ?, ?, ?)
        """,
        (sku_id, price_type, new_price, reference_price, reason),
    )
