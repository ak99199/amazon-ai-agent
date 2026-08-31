"""Normalized, seller-scoped internal alert domain model."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json

ALERT_STATUSES = ("new", "sent", "dismissed")
ALERT_SEVERITIES = ("info", "medium", "high", "critical")


def alert_dedupe_key(seller_id: str, marketplace_id: str, asin: str, alert_type: str, relevant_state: dict) -> str:
    """Create a stable, non-secret key for one meaningful alert state."""
    payload = {"seller_id": seller_id, "marketplace_id": marketplace_id, "asin": asin, "alert_type": alert_type, "state": relevant_state}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Alert:
    alert_id: str
    seller_id: str
    marketplace_id: str
    asin: str
    alert_type: str
    severity: str
    title: str
    message: str
    action_code: str
    created_at: datetime
    dedupe_key: str
    status: str = "new"

    def public_dict(self) -> dict:
        value = asdict(self)
        value["created_at"] = self.created_at.isoformat()
        return value