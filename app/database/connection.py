"""SQLite connection and schema initialization utilities."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

DATABASE_PATH = Path("data") / "amazon_ai_agent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS listing_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id TEXT NOT NULL,
    marketplace_id TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    sku TEXT NOT NULL,
    asin TEXT NOT NULL,
    title TEXT,
    brand TEXT,
    product_type TEXT,
    condition TEXT,
    listing_status TEXT,
    price TEXT,
    currency TEXT,
    fulfillment_channel TEXT,
    listing_hash TEXT NOT NULL,
    changed INTEGER NOT NULL CHECK (changed IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_listing_scope_asin_captured
ON listing_snapshots (seller_id, marketplace_id, asin, captured_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_listing_scope_changed_captured
ON listing_snapshots (seller_id, marketplace_id, changed, captured_at DESC, id DESC);
"""

def initialize_database(database_path: Path | str = DATABASE_PATH) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)

@contextmanager
def get_connection(database_path: Path | str = DATABASE_PATH):
    initialize_database(database_path)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
