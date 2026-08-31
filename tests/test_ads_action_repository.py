from datetime import datetime, timezone
from app.amazon_ads.action_models import AdsRecommendationDecision
from app.database.ads_repository import AdsPerformanceRepository


def decision(status="approved", note="Looks valid"):
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return AdsRecommendationDecision("recommendation", "seller", "market", "profile", "campaign", "campaign-1", "HIGH_ACOS", "Review high ACOS", status, note, created_at=stamp, updated_at=stamp, reviewed_at=stamp)


def test_decision_is_idempotent_audited_and_scoped(tmp_path):
    repository = AdsPerformanceRepository(tmp_path / "ads.db")
    first = repository.save_decision(decision())
    repeated = repository.save_decision(decision())
    assert first.stable_decision_id == repeated.stable_decision_id
    assert len(repository.list_decision_events("seller", "market", "profile", "recommendation")) == 1
    updated = repository.save_decision(decision("rejected", "Declined"))
    assert updated.status == "rejected"
    assert len(repository.list_decision_events("seller", "market", "profile", "recommendation")) == 2
    assert repository.get_decision("other", "market", "profile", "recommendation") is None
    assert repository.get_decision("seller", "other", "profile", "recommendation") is None
    assert repository.get_decision("seller", "market", "other", "recommendation") is None


def test_decision_status_filter(tmp_path):
    repository = AdsPerformanceRepository(tmp_path / "ads.db")
    repository.save_decision(decision("approved"))
    assert len(repository.list_decisions("seller", "market", "profile", "approved")) == 1
    assert repository.list_decisions("seller", "market", "profile", "dismissed") == []
