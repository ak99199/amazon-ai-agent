from datetime import datetime, timezone
from app.amazon_ads.action_models import AdsRecommendationDecision
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_recommendation_effectiveness_service import AdsRecommendationEffectivenessService


def decision(identifier, status, code="HIGH_ACOS", snapshot=None):
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    return AdsRecommendationDecision(identifier, "seller", "market", "profile", "campaign", identifier, code, code, status, "private note", "test", created_at=now, updated_at=now, reviewed_at=now, recommendation_snapshot=snapshot)


def test_effectiveness_uses_current_decisions_and_safe_feedback(tmp_path):
    repository = AdsPerformanceRepository(tmp_path / "ads.db")
    snapshot = {"priority": "high", "confidence": "high", "window_days": 30, "metrics_snapshot": {"spend": "10"}, "suggested_action": "review", "suggested_bid_direction": None}
    repository.save_decision(decision("approved", "approved", snapshot=snapshot))
    repository.save_decision(decision("rejected", "rejected", snapshot=snapshot))
    service = AdsRecommendationEffectivenessService(repository, now=lambda: datetime(2026, 1, 11, tzinfo=timezone.utc), min_reviewed_sample=2)
    result = service.get("seller", "market", "profile", 7).public_dict()
    assert result["total_reviewed"] == 2 and result["approval_rate"] == "50.0" and result["rejection_rate"] == "50.0"
    feedback = service.feedback("seller", "market", "profile", 7)[0].public_dict()
    assert feedback["review_note_present"] is True and "review_note" not in feedback and feedback["snapshot_available"] is True