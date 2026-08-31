"""Internal human-review records for deterministic Ads recommendations."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

VALID_DECISION_STATUSES = frozenset({"pending", "approved", "rejected", "dismissed"})


@dataclass(frozen=True)
class AdsRecommendationDecision:
    recommendation_id: str
    seller_id: str
    marketplace_id: str
    profile_id: str
    scope_type: str
    scope_id: str
    recommendation_code: str
    recommendation_title: str
    status: str = "pending"
    review_note: str | None = None
    review_source: str = "dashboard"
    decision_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    reviewed_at: datetime | None = None
    recommendation_snapshot: dict | None = None

    def __post_init__(self):
        if self.status not in VALID_DECISION_STATUSES:
            raise ValueError("Unsupported Ads recommendation decision status")

    @property
    def stable_decision_id(self) -> str:
        if self.decision_id:
            return self.decision_id
        value = "|".join((self.seller_id, self.marketplace_id, self.profile_id, self.recommendation_id))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

    def public_dict(self) -> dict[str, object]:
        iso = lambda value: value.isoformat() if isinstance(value, datetime) else value
        return {
            "decision_id": self.stable_decision_id,
            "recommendation_id": self.recommendation_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "recommendation_code": self.recommendation_code,
            "recommendation_title": self.recommendation_title,
            "status": self.status,
            "review_note": self.review_note,
            "reviewed_at": iso(self.reviewed_at),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


@dataclass(frozen=True)
class AdsRecommendationDecisionEvent:
    event_id: str
    decision_id: str
    recommendation_id: str
    seller_id: str
    marketplace_id: str
    profile_id: str
    old_status: str | None
    new_status: str
    review_note: str | None
    review_source: str
    created_at: datetime
