import sqlite3
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    site TEXT NOT NULL,
    sku_id TEXT NOT NULL,
    product_id TEXT,
    display_name TEXT,
    brand TEXT,
    seller_id TEXT,
    seller_name TEXT,
    url TEXT,
    media_url TEXT,
    first_seen_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT,
    PRIMARY KEY (site, sku_id)
);

CREATE TABLE IF NOT EXISTS price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site TEXT NOT NULL,
    sku_id TEXT NOT NULL,
    price_type TEXT NOT NULL,
    price INTEGER NOT NULL,
    search_term TEXT,
    observed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (site, sku_id) REFERENCES products(site, sku_id)
);

CREATE INDEX IF NOT EXISTS idx_price_obs_site_sku_type
    ON price_observations (site, sku_id, price_type, observed_at);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site TEXT NOT NULL,
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


def upsert_product(conn, site, sku_id, product_id, display_name, brand, seller_id, seller_name, url, media_url):
    conn.execute(
        """
        INSERT INTO products (site, sku_id, product_id, display_name, brand, seller_id, seller_name, url, media_url, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(site, sku_id) DO UPDATE SET
            product_id=excluded.product_id,
            display_name=excluded.display_name,
            brand=excluded.brand,
            seller_id=excluded.seller_id,
            seller_name=excluded.seller_name,
            url=excluded.url,
            media_url=excluded.media_url,
            last_seen_at=datetime('now')
        """,
        (site, sku_id, product_id, display_name, brand, seller_id, seller_name, url, media_url),
    )


def get_price_history(conn, site, sku_id, price_type, limit=20):
    rows = conn.execute(
        """
        SELECT price FROM price_observations
        WHERE site = ? AND sku_id = ? AND price_type = ?
        ORDER BY observed_at DESC
        LIMIT ?
        """,
        (site, sku_id, price_type, limit),
    ).fetchall()
    return [row["price"] for row in rows]


def insert_observation(conn, site, sku_id, price_type, price, search_term):
    conn.execute(
        """
        INSERT INTO price_observations (site, sku_id, price_type, price, search_term)
        VALUES (?, ?, ?, ?, ?)
        """,
        (site, sku_id, price_type, price, search_term),
    )


def get_last_alert_price(conn, site, sku_id, price_type):
    # Se ordena por id (no por created_at): datetime('now') en SQLite solo
    # tiene resolución de 1 segundo, así que dos alertas en el mismo segundo
    # no se pueden distinguir de forma confiable por fecha.
    row = conn.execute(
        """
        SELECT new_price FROM alerts
        WHERE site = ? AND sku_id = ? AND price_type = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (site, sku_id, price_type),
    ).fetchone()
    return row["new_price"] if row else None


def insert_alert(conn, site, sku_id, price_type, new_price, reference_price, reason):
    conn.execute(
        """
        INSERT INTO alerts (site, sku_id, price_type, new_price, reference_price, reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (site, sku_id, price_type, new_price, reference_price, reason),
    )
