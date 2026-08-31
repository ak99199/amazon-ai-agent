"""Domain models and deterministic listing snapshot hashing."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from app.amazon.models import Listing

_HASH_FIELDS = ("sku", "asin", "title", "brand", "product_type", "condition", "listing_status", "price", "currency", "fulfillment_channel")

def listing_hash(listing: Listing) -> str:
    values = {field: getattr(listing, field) for field in _HASH_FIELDS}
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class ListingSnapshot:
    id: int | None
    seller_id: str
    marketplace_id: str
    captured_at: datetime
    sku: str
    asin: str
    title: str | None
    brand: str | None
    product_type: str | None
    condition: str | None
    listing_status: str | None
    price: str | None
    currency: str | None
    fulfillment_channel: str | None
    listing_hash: str
    changed: bool

    @classmethod
    def from_listing(cls, listing: Listing, changed: bool = True, captured_at: datetime | None = None):
        if not listing.asin:
            raise ValueError("Listing snapshots require an ASIN")
        return cls(None, listing.seller_id, listing.marketplace_id, captured_at or datetime.now(timezone.utc), listing.sku, listing.asin, listing.title, listing.brand, listing.product_type, listing.condition, listing.listing_status, listing.price, listing.currency, listing.fulfillment_channel, listing_hash(listing), changed)

    def public_dict(self) -> dict:
        return {"id": self.id, "seller_id": self.seller_id, "marketplace_id": self.marketplace_id, "captured_at": self.captured_at.isoformat(), "sku": self.sku, "asin": self.asin, "title": self.title, "brand": self.brand, "product_type": self.product_type, "condition": self.condition, "listing_status": self.listing_status, "price": self.price, "currency": self.currency, "fulfillment_channel": self.fulfillment_channel, "changed": self.changed}
