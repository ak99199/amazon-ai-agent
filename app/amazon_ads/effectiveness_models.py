"""Safe, internal Amazon Ads recommendation feedback models."""
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal


def _public(value):
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, dict): return {key: _public(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [_public(item) for item in value]
    return value


@dataclass(frozen=True)
class AdsRecommendationEffectivenessSummary:
    window_days: int | None
    start_date: datetime | None
    end_date: datetime
    total_reviewed: int
    total_pending: int
    total_approved: int
    total_rejected: int
    total_dismissed: int
    approval_rate: Decimal | None
    rejection_rate: Decimal | None
    dismissal_rate: Decimal | None
    by_code: list[dict]
    by_priority: list[dict]
    by_scope_type: list[dict]
    repeated_rejection_codes: list[str]
    high_approval_codes: list[str]
    feedback_sample_count: int
    def public_dict(self): return _public(asdict(self))


@dataclass(frozen=True)
class AdsRecommendationFeedbackRecord:
    recommendation_id: str
    decision_id: str
    seller_id: str
    marketplace_id: str
    profile_id: str
    recommendation_code: str
    scope_type: str
    scope_id: str
    priority: str | None
    confidence: str | None
    window_days: int | None
    decision_status: str
    review_note_present: bool
    reviewed_at: datetime | None
    metrics_snapshot: dict | None
    suggested_action: str | None
    suggested_bid_direction: str | None
    snapshot_available: bool
    def public_dict(self): return _public(asdict(self))