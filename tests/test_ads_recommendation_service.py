from datetime import date, datetime, timezone
from decimal import Decimal
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.services.ads_recommendation_service import AdsRecommendationService
from app.services.ads_signal_service import AdsRecommendationThresholds, AdsSignalService


class Repository:
    def __init__(self, rows): self.rows = rows
    def list_window(self, seller_id, marketplace_id, profile_id, days, reference_date=None, **filters):
        assert (seller_id, marketplace_id, profile_id) == ("seller", "market", "profile")
        return [row for row in self.rows if all(filters.get(name) is None or getattr(row, name) == filters[name] for name in ("campaign_id", "keyword_id", "search_term"))]


def row(day, spend="100", orders=0, sales="0", term="term", keyword="keyword"):
    return AdsPerformanceDaily("seller", "market", "profile", date(2026, 1, day), "SP", "campaign", "Campaign", keyword_id=keyword, keyword_text="Keyword", search_term=term, impressions=500, clicks=20, spend=Decimal(spend), orders=orders, units=orders, sales=Decimal(sales))


def service(rows):
    thresholds = AdsRecommendationThresholds(wasted_spend_threshold=Decimal("50"), target_acos_percent=Decimal("30"), high_cpc_amount=Decimal("100"))
    return AdsRecommendationService(Repository(rows), signals=AdsSignalService(thresholds), now=lambda: datetime(2026, 2, 1, tzinfo=timezone.utc))


def test_recommendations_are_scoped_deterministic_and_no_conflicting_bid_direction():
    output = service([row(day) for day in range(1, 15)]).get_search_term_recommendations("seller", "market", "profile", window=30)
    codes = {item.recommendation_code for item in output}
    assert {"WASTED_SPEND", "NEGATIVE_KEYWORD_CANDIDATE", "BID_DECREASE_CANDIDATE"} <= codes
    assert "BID_INCREASE_CANDIDATE" not in codes
    public = output[0].public_dict()
    assert public["seller_id"] == "seller" and "access_token" not in public and "authorization" not in public


def test_profitable_search_term_is_candidate_not_automation():
    output = service([row(day, "20", 2, "200") for day in range(1, 15)]).get_search_term_recommendations("seller", "market", "profile", window=30)
    codes = {item.recommendation_code for item in output}
    assert "PROFITABLE_SEARCH_TERM" in codes and "KEYWORD_HARVEST_CANDIDATE" in codes
    assert all("no keyword is created" in item.suggested_action.lower() or item.recommendation_code != "KEYWORD_HARVEST_CANDIDATE" for item in output)

