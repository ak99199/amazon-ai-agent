from decimal import Decimal
import pytest
from app.amazon_ads.search_terms import SearchTermReportService
from app.amazon_ads.reporting import AdsReportNormalizationError
def raw(**x):return {"date":"2026-01-01","campaignId":"c","searchTerm":"term","impressions":0,"clicks":"0","cost":"0","purchases14d":0,"unitsSold14d":0,"sales14d":"0"}|x
def test_search_term_normalizes_zero_and_ignores_unknown():
 value=SearchTermReportService().normalize_row("s","m","p",raw(extra="ignored"));assert value.search_term=="term" and value.spend==Decimal("0")
def test_search_term_rejects_bad_money():
 with pytest.raises(AdsReportNormalizationError):SearchTermReportService().normalize_row("s","m","p",raw(cost="bad"))