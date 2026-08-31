"""Normalized, secret-free Amazon Ads intelligence payloads."""
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal


def _public(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _public(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_public(item) for item in value]
    return value


@dataclass(frozen=True)
class AdsIntelligenceSummary:
    window_days: int
    start_date: date
    end_date: date
    summary: dict[str, object]
    trend: list[dict[str, object]]
    comparison: dict[str, object]
    top_campaigns: list[dict[str, object]]
    weak_campaigns: list[dict[str, object]]
    top_keywords: list[dict[str, object]]
    weak_keywords: list[dict[str, object]]
    profitable_search_terms: list[dict[str, object]]
    wasted_search_terms: list[dict[str, object]]
    recommendations: dict[str, object]
    decisions: dict[str, object]
    sync_health: dict[str, object]

    def public_dict(self):
        return _public(asdict(self))