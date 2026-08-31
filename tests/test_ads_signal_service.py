from datetime import date
from decimal import Decimal
import pytest
from app.services.ads_signal_service import AdsRecommendationConfigurationError, AdsRecommendationThresholds, AdsSignalService
from app.services.ads_metrics_service import AdsMetricsService


def metrics(impressions=1000, clicks=30, spend="100", orders=3, sales="400"):
    return AdsMetricsService.calculate(impressions, clicks, Decimal(spend), orders, orders, Decimal(sales))


def test_signal_codes_cover_insufficient_and_negative_rules():
    service = AdsSignalService(AdsRecommendationThresholds(wasted_spend_threshold=Decimal("50"), high_cpc_amount=Decimal("2")))
    assert service.codes(metrics(10, 1, "1", 0, "0"), 1, "campaign") == ("INSUFFICIENT_DATA",)
    codes = service.codes(metrics(1000, 30, "100", 0, "0"), 14, "search_term")
    assert "WASTED_SPEND" in codes and "NEGATIVE_KEYWORD_CANDIDATE" in codes and "BID_DECREASE_CANDIDATE" in codes
    assert "BID_INCREASE_CANDIDATE" not in codes


def test_signal_codes_cover_positive_and_stable_rules():
    service = AdsSignalService(AdsRecommendationThresholds())
    positive = service.codes(metrics(1000, 30, "60", 3, "600"), 14, "search_term")
    assert "PROFITABLE_SEARCH_TERM" in positive and "KEYWORD_HARVEST_CANDIDATE" in positive
    stable = service.codes(metrics(1000, 30, "120", 3, "400"), 14, "campaign")
    assert stable == ("KEEP_STABLE",)


def test_thresholds_are_strict_and_decimal_safe(monkeypatch):
    monkeypatch.setenv("AMAZON_ADS_TARGET_ACOS_PERCENT", "25.5")
    assert AdsRecommendationThresholds.from_environment().target_acos_percent == Decimal("25.5")
    monkeypatch.setenv("AMAZON_ADS_TARGET_ACOS_PERCENT", "not-a-number")
    with pytest.raises(AdsRecommendationConfigurationError):
        AdsRecommendationThresholds.from_environment()


