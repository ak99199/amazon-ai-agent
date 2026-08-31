"""Deterministic history and trend calculations for listing snapshots."""
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from app.amazon.models import Listing
from app.database.repository import ListingSnapshotRepository

@dataclass(frozen=True)
class ListingTrend:
    first_seen: str | None
    last_seen: str | None
    price_change: str | None
    title_changed: bool
    status_changed: bool
    number_of_snapshots: int
    days_tracked: int
    def public_dict(self): return asdict(self)

class ListingHistoryService:
    def __init__(self, repository: ListingSnapshotRepository): self._repository=repository
    def save_current_listings(self, listings: list[Listing]):
        """Explicitly persist already-normalized listings; this never calls Amazon."""
        return [self._repository.save_listing_snapshot(listing) for listing in listings if listing.asin]
    def get_history(self, seller_id, marketplace_id, asin, limit=30):
        return self._repository.get_listing_history(seller_id,marketplace_id,asin,limit)
    def get_trend(self, seller_id, marketplace_id, asin, limit=30):
        history=self.get_history(seller_id,marketplace_id,asin,limit)
        if not history: return ListingTrend(None,None,None,False,False,0,0)
        ordered=sorted(history,key=lambda item:(item.captured_at,item.id or 0)); first,last=ordered[0],ordered[-1]
        return ListingTrend(first.captured_at.isoformat(),last.captured_at.isoformat(),self._price_change(first.price,last.price),first.title != last.title,first.listing_status != last.listing_status,len(ordered),(last.captured_at.date()-first.captured_at.date()).days)
    @staticmethod
    def _price_change(first, last):
        if first is None or last is None: return None
        try: return str(Decimal(last)-Decimal(first))
        except (InvalidOperation, ValueError): return None
