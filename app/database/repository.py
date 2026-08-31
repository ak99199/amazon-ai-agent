"""Seller- and marketplace-isolated snapshot repository."""
from datetime import datetime
from pathlib import Path
from app.amazon.models import Listing
from app.database.connection import DATABASE_PATH, get_connection
from app.database.models import ListingSnapshot

class ListingSnapshotRepository:
    def __init__(self, database_path: Path | str = DATABASE_PATH): self._database_path = database_path
    def save_listing_snapshot(self, listing: Listing, captured_at: datetime | None = None) -> ListingSnapshot:
        candidate = ListingSnapshot.from_listing(listing, captured_at=captured_at)
        latest = self.get_latest_listing(candidate.seller_id, candidate.marketplace_id, candidate.asin)
        changed = latest is None or latest.listing_hash != candidate.listing_hash
        snapshot = ListingSnapshot.from_listing(listing, changed=changed, captured_at=candidate.captured_at)
        columns = ("seller_id","marketplace_id","captured_at","sku","asin","title","brand","product_type","condition","listing_status","price","currency","fulfillment_channel","listing_hash","changed")
        values = (snapshot.seller_id,snapshot.marketplace_id,snapshot.captured_at.isoformat(),snapshot.sku,snapshot.asin,snapshot.title,snapshot.brand,snapshot.product_type,snapshot.condition,snapshot.listing_status,snapshot.price,snapshot.currency,snapshot.fulfillment_channel,snapshot.listing_hash,int(snapshot.changed))
        with get_connection(self._database_path) as connection:
            cursor=connection.execute(f"INSERT INTO listing_snapshots ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",values)
            snapshot_id=cursor.lastrowid
        return ListingSnapshot(snapshot_id,*values[:2],snapshot.captured_at,*values[3:-1],snapshot.changed)
    def get_latest_listing(self, seller_id: str, marketplace_id: str, asin: str) -> ListingSnapshot | None:
        return self._one("SELECT * FROM listing_snapshots WHERE seller_id=? AND marketplace_id=? AND asin=? ORDER BY captured_at DESC,id DESC LIMIT 1",(seller_id,marketplace_id,asin))
    def get_listing_history(self, seller_id: str, marketplace_id: str, asin: str, limit: int = 30) -> list[ListingSnapshot]:
        safe_limit=max(1,min(limit,100)); return self._many("SELECT * FROM listing_snapshots WHERE seller_id=? AND marketplace_id=? AND asin=? ORDER BY captured_at DESC,id DESC LIMIT ?",(seller_id,marketplace_id,asin,safe_limit))
    def find_changed_listings(self, seller_id: str, marketplace_id: str, since_timestamp: datetime) -> list[ListingSnapshot]:
        return self._many("SELECT * FROM listing_snapshots WHERE seller_id=? AND marketplace_id=? AND changed=1 AND captured_at>=? ORDER BY captured_at DESC,id DESC",(seller_id,marketplace_id,since_timestamp.isoformat()))
    def count_snapshots(self, seller_id: str, marketplace_id: str) -> int:
        with get_connection(self._database_path) as connection: return int(connection.execute("SELECT COUNT(*) FROM listing_snapshots WHERE seller_id=? AND marketplace_id=?",(seller_id,marketplace_id)).fetchone()[0])
    def _one(self,query,params):
        rows=self._many(query,params); return rows[0] if rows else None
    def _many(self,query,params):
        with get_connection(self._database_path) as connection: rows=connection.execute(query,params).fetchall()
        return [self._row_to_snapshot(row) for row in rows]
    @staticmethod
    def _row_to_snapshot(row):
        return ListingSnapshot(row["id"],row["seller_id"],row["marketplace_id"],datetime.fromisoformat(row["captured_at"]),row["sku"],row["asin"],row["title"],row["brand"],row["product_type"],row["condition"],row["listing_status"],row["price"],row["currency"],row["fulfillment_channel"],row["listing_hash"],bool(row["changed"]))
