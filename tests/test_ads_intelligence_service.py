from datetime import date
from decimal import Decimal

from app.amazon_ads.report_models import AdsPerformanceDaily
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_intelligence_service import AdsIntelligenceService


def row(day, campaign="c1", keyword="k1", term="term", spend="10", sales="50", clicks=10, orders=2):
    return AdsPerformanceDaily("seller", "market", "profile", day, "SP", campaign, "Campaign", keyword_id=keyword, keyword_text="Keyword", search_term=term, impressions=100, clicks=clicks, spend=Decimal(spend), orders=orders, units=orders, sales=Decimal(sales))


def test_intelligence_aggregates_base_metrics_then_derives_rates(tmp_path):
    repository = AdsPerformanceRepository(tmp_path / "ads.db")
    repository.save_many([row(date(2026, 1, 29)), row(date(2026, 1, 30), spend="35", sales="40", clicks=20, orders=4)])
    service = AdsIntelligenceService(repository, today=lambda: date(2026, 1, 30))
    result = service.get("seller", "market", "profile", 7, reference_date=date(2026, 1, 30)).public_dict()
    totals = result["summary"]["totals"]
    assert totals["spend"] == "45" and totals["sales"] == "90"
    assert totals["ctr"] == "15.00" and totals["cpc"] == "1.5"
    assert totals["cvr"] == "20.0" and totals["acos"] == "50.0" and totals["roas"] == "2"
    assert [point["date"] for point in result["trend"]] == ["2026-01-29", "2026-01-30"]


def test_intelligence_empty_data_is_safe_and_isolated(tmp_path):
    repository = AdsPerformanceRepository(tmp_path / "ads.db")
    repository.save(row(date(2026, 1, 30)))
    service = AdsIntelligenceService(repository, today=lambda: date(2026, 1, 30))
    empty = service.get("other", "market", "profile", 7).public_dict()
    totals = empty["summary"]["totals"]
    assert totals["impressions"] == 0 and totals["clicks"] == 0
    assert totals["ctr"] is None and totals["cpc"] is None and totals["cvr"] is None
    assert totals["acos"] is None and totals["roas"] is None
    assert empty["trend"] == [] and empty["comparison"]["spend_change_percent"] is None
    assert service.get("seller", "market", "profile", 7).public_dict()["summary"]["totals"]["spend"] == "10"