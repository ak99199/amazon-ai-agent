"""Normalized, serializable, recommendation-only Amazon Ads models."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json


@dataclass(frozen=True)
class AdsRecommendation:
    seller_id: str
    marketplace_id: str
    profile_id: str
    scope_type: str
    scope_id: str
    scope_label: str
    recommendation_code: str
    priority: str
    confidence: str
    title: str
    summary: str
    reason: str
    window_days: int
    metrics_snapshot: dict[str, object]
    suggested_action: str
    suggested_bid_direction: str | None = None
    suggested_budget_direction: str | None = None
    created_at: datetime | None = None
    rule_version_id: str | None = None
    rule_version_name: str | None = None
    rule_version_source: str | None = None

    @property
    def recommendation_id(self) -> str:
        value = "|".join((self.seller_id, self.marketplace_id, self.profile_id, self.scope_type, self.scope_id, self.recommendation_code, str(self.window_days)))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

    def public_dict(self) -> dict[str, object]:
        metrics = {key: (str(value) if isinstance(value, Decimal) else value) for key, value in self.metrics_snapshot.items()}
        return {
            "recommendation_id": self.recommendation_id,
            "seller_id": self.seller_id,
            "marketplace_id": self.marketplace_id,
            "profile_id": self.profile_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "scope_label": self.scope_label,
            "recommendation_code": self.recommendation_code,
            "priority": self.priority,
            "confidence": self.confidence,
            "title": self.title,
            "summary": self.summary,
            "reason": self.reason,
            "window_days": self.window_days,
            "metrics_snapshot": metrics,
            "suggested_action": self.suggested_action,
            "rule_version_id": self.rule_version_id,
            "rule_version_name": self.rule_version_name,
            "rule_version_source": self.rule_version_source,
            "suggested_bid_direction": self.suggested_bid_direction,
            "suggested_budget_direction": self.suggested_budget_direction,
            "created_at": (self.created_at or datetime.now(timezone.utc)).isoformat(),
        }
