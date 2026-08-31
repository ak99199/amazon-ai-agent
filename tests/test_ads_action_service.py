from datetime import datetime, timezone
import pytest
from app.amazon_ads.recommendation_models import AdsRecommendation
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_action_service import AdsActionService, UnknownAdsRecommendationError


def recommendation():
    return AdsRecommendation("seller", "market", "profile", "campaign", "campaign-1", "Campaign", "HIGH_ACOS", "high", "high", "Review high ACOS", "Summary", "Reason", 30, {"spend": "100"}, "Human review only")


class Recommendations:
    def get_recommendations(self, *args, **kwargs): return [recommendation()]


def service(tmp_path):
    return AdsActionService(Recommendations(), AdsPerformanceRepository(tmp_path / "ads.db"), now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_actions_merge_virtual_pending_and_human_decision(tmp_path):
    actions = service(tmp_path)
    listed = actions.list_actions("seller", "market", "profile")
    assert listed["pending_count"] == 1 and listed["actions"][0]["status"] == "pending"
    saved = actions.set_decision("seller", "market", "profile", recommendation().recommendation_id, "approved", "  accepted  ")
    assert saved.status == "approved" and saved.review_note == "accepted"
    assert actions.list_actions("seller", "market", "profile")["approved_count"] == 1
    actions.set_decision("seller", "market", "profile", recommendation().recommendation_id, "rejected")
    assert actions.list_actions("seller", "market", "profile")["rejected_count"] == 1
    actions.set_decision("seller", "market", "profile", recommendation().recommendation_id, "dismissed")
    assert actions.list_actions("seller", "market", "profile")["dismissed_count"] == 1


def test_actions_reject_invalid_status_unknown_id_and_long_note(tmp_path):
    actions = service(tmp_path)
    with pytest.raises(ValueError): actions.set_decision("seller", "market", "profile", recommendation().recommendation_id, "pending")
    with pytest.raises(UnknownAdsRecommendationError): actions.set_decision("seller", "market", "profile", "unknown", "approved")
    with pytest.raises(ValueError): actions.set_decision("seller", "market", "profile", recommendation().recommendation_id, "approved", "x" * 1001)

