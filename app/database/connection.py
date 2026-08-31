"""SQLite connection and schema initialization utilities."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
DATABASE_PATH=Path("data")/"amazon_ai_agent.db"
SCHEMA="""
CREATE TABLE IF NOT EXISTS listing_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,captured_at TEXT NOT NULL,sku TEXT NOT NULL,asin TEXT NOT NULL,title TEXT,brand TEXT,product_type TEXT,condition TEXT,listing_status TEXT,price TEXT,currency TEXT,fulfillment_channel TEXT,listing_hash TEXT NOT NULL,changed INTEGER NOT NULL CHECK (changed IN (0,1)));
CREATE INDEX IF NOT EXISTS idx_listing_scope_asin_captured ON listing_snapshots (seller_id,marketplace_id,asin,captured_at DESC,id DESC);
CREATE TABLE IF NOT EXISTS snapshot_runs (id INTEGER PRIMARY KEY AUTOINCREMENT,started_at TEXT NOT NULL,finished_at TEXT NOT NULL,success INTEGER NOT NULL CHECK (success IN (0,1)),listings_fetched INTEGER NOT NULL,snapshots_saved INTEGER NOT NULL,changed_count INTEGER NOT NULL,unchanged_count INTEGER NOT NULL,failed_count INTEGER NOT NULL,pages_processed INTEGER NOT NULL,error_summary TEXT);
CREATE TABLE IF NOT EXISTS alerts (alert_id TEXT PRIMARY KEY,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,asin TEXT NOT NULL,alert_type TEXT NOT NULL,severity TEXT NOT NULL CHECK (severity IN ('info','medium','high','critical')),title TEXT NOT NULL,message TEXT NOT NULL,action_code TEXT NOT NULL,created_at TEXT NOT NULL,dedupe_key TEXT NOT NULL,status TEXT NOT NULL CHECK (status IN ('new','sent','dismissed')),UNIQUE(seller_id,marketplace_id,dedupe_key));
CREATE INDEX IF NOT EXISTS idx_alerts_scope_status_created ON alerts (seller_id,marketplace_id,status,created_at DESC);
"""
def initialize_database(database_path=DATABASE_PATH):
    path=Path(database_path); path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as connection: connection.executescript(SCHEMA)
@contextmanager
def get_connection(database_path=DATABASE_PATH):
    initialize_database(database_path); connection=sqlite3.connect(database_path); connection.row_factory=sqlite3.Row
    try: yield connection; connection.commit()
    finally: connection.close()