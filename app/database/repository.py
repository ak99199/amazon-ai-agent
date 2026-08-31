"""Seller-isolated listing snapshots and safe collection-run metadata."""
from datetime import datetime
from pathlib import Path
from app.amazon.models import Listing
from app.database.connection import DATABASE_PATH,get_connection
from app.database.models import ListingSnapshot
class ListingSnapshotRepository:
    def __init__(self,database_path:Path|str=DATABASE_PATH): self._database_path=database_path
    def save_listing_snapshot(self,listing:Listing,captured_at:datetime|None=None):
        candidate=ListingSnapshot.from_listing(listing,captured_at=captured_at); latest=self.get_latest_listing(candidate.seller_id,candidate.marketplace_id,candidate.asin); changed=latest is None or latest.listing_hash != candidate.listing_hash; snapshot=ListingSnapshot.from_listing(listing,changed,candidate.captured_at)
        columns=("seller_id","marketplace_id","captured_at","sku","asin","title","brand","product_type","condition","listing_status","price","currency","fulfillment_channel","listing_hash","changed"); values=(snapshot.seller_id,snapshot.marketplace_id,snapshot.captured_at.isoformat(),snapshot.sku,snapshot.asin,snapshot.title,snapshot.brand,snapshot.product_type,snapshot.condition,snapshot.listing_status,snapshot.price,snapshot.currency,snapshot.fulfillment_channel,snapshot.listing_hash,int(snapshot.changed))
        with get_connection(self._database_path) as connection: snapshot_id=connection.execute(f"INSERT INTO listing_snapshots ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",values).lastrowid
        return ListingSnapshot(snapshot_id,snapshot.seller_id,snapshot.marketplace_id,snapshot.captured_at,snapshot.sku,snapshot.asin,snapshot.title,snapshot.brand,snapshot.product_type,snapshot.condition,snapshot.listing_status,snapshot.price,snapshot.currency,snapshot.fulfillment_channel,snapshot.listing_hash,snapshot.changed)
    def get_latest_listing(self,seller_id,marketplace_id,asin):
        records=self._query("SELECT * FROM listing_snapshots WHERE seller_id=? AND marketplace_id=? AND asin=? ORDER BY captured_at DESC,id DESC LIMIT 1",(seller_id,marketplace_id,asin)); return records[0] if records else None
    def get_listing_history(self,seller_id,marketplace_id,asin,limit=30): return self._query("SELECT * FROM listing_snapshots WHERE seller_id=? AND marketplace_id=? AND asin=? ORDER BY captured_at DESC,id DESC LIMIT ?",(seller_id,marketplace_id,asin,max(1,min(limit,100))))
    def find_changed_listings(self,seller_id,marketplace_id,since_timestamp): return self._query("SELECT * FROM listing_snapshots WHERE seller_id=? AND marketplace_id=? AND changed=1 AND captured_at>=? ORDER BY captured_at DESC,id DESC",(seller_id,marketplace_id,since_timestamp.isoformat()))
    def count_snapshots(self,seller_id,marketplace_id):
        with get_connection(self._database_path) as connection: return connection.execute("SELECT COUNT(*) FROM listing_snapshots WHERE seller_id=? AND marketplace_id=?",(seller_id,marketplace_id)).fetchone()[0]
    def save_snapshot_run(self,result):
        values=(result.started_at.isoformat(),result.finished_at.isoformat(),int(result.success),result.listings_fetched,result.snapshots_saved,result.changed_count,result.unchanged_count,result.failed_count,result.pages_processed,"; ".join(result.errors) or None)
        with get_connection(self._database_path) as connection: return connection.execute("INSERT INTO snapshot_runs (started_at,finished_at,success,listings_fetched,snapshots_saved,changed_count,unchanged_count,failed_count,pages_processed,error_summary) VALUES (?,?,?,?,?,?,?,?,?,?)",values).lastrowid
    def count_snapshot_runs(self):
        with get_connection(self._database_path) as connection: return connection.execute("SELECT COUNT(*) FROM snapshot_runs").fetchone()[0]
    def list_tracked_asins(self,seller_id,marketplace_id):
        with get_connection(self._database_path) as connection: rows=connection.execute("SELECT DISTINCT asin FROM listing_snapshots WHERE seller_id=? AND marketplace_id=? ORDER BY asin",(seller_id,marketplace_id)).fetchall()
        return [row[0] for row in rows]
    def _query(self,query,params):
        with get_connection(self._database_path) as connection: rows=connection.execute(query,params).fetchall()
        return [ListingSnapshot(row["id"],row["seller_id"],row["marketplace_id"],datetime.fromisoformat(row["captured_at"]),row["sku"],row["asin"],row["title"],row["brand"],row["product_type"],row["condition"],row["listing_status"],row["price"],row["currency"],row["fulfillment_channel"],row["listing_hash"],bool(row["changed"])) for row in rows]

