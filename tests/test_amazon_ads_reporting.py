from datetime import date
from decimal import Decimal
import pytest
from app.amazon_ads.reporting import AdsReportNormalizationError,SponsoredProductsReportingService

def service():return SponsoredProductsReportingService()
def row(**overrides):return {"date":"2026-01-10","campaignId":"c1","campaignName":"Campaign","impressions":"100","clicks":4,"cost":"12.34","purchases14d":"2","unitsSold14d":2,"sales14d":50,"currency":"INR"}|overrides
def test_report_requests_support_future_levels():
    value=service();assert value.build_request("campaign",date(2026,1,1),date(2026,1,2)).ad_product=="SP" and value.build_request("search_term",date(2026,1,1),date(2026,1,2)).group_by==("campaignId","adGroupId","searchTerm")
def test_normalizes_optional_dimensions_and_numbers():
    value=service().normalize_row("seller","market","profile",row(keywordId=None,searchTerm=None))
    assert value.keyword_id is None and value.search_term is None and value.impressions==100 and value.spend==Decimal("12.34") and value.sales==Decimal("50")
def test_invalid_money_rejected_and_empty_rows_are_safe():
    with pytest.raises(AdsReportNormalizationError):service().normalize_row("seller","market","profile",row(cost="not-money"))
    assert service().normalize_rows("seller","market","profile",[])==[]