from datetime import date
from decimal import Decimal
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.services.ads_metrics_service import AdsMetricsService

def row(impressions=100,clicks=10,spend="20",orders=2,units=3,sales="100"):
    return AdsPerformanceDaily("s","m","p",date(2026,1,1),"SP",impressions=impressions,clicks=clicks,spend=Decimal(spend),orders=orders,units=units,sales=Decimal(sales))
def test_metrics_are_decimal_and_safe():
    metrics=AdsMetricsService.calculate(100,10,Decimal("20"),2,3,Decimal("100"));assert metrics["ctr"]==Decimal("10") and metrics["cpc"]==Decimal("2") and metrics["cvr"]==Decimal("20") and metrics["acos"]==Decimal("20") and metrics["roas"]==Decimal("5")
    zero=AdsMetricsService.calculate(0,0,0,0,0,0);assert all(zero[key] is None for key in ("ctr","cpc","cvr","acos","roas"))
def test_aggregate_derives_metrics_from_totals():
    metrics=AdsMetricsService().aggregate([row(100,10,"20",2,3,"100"),row(100,0,"10",0,0,"0")]);assert metrics["impressions"]==200 and metrics["spend"]==Decimal("30") and metrics["ctr"]==Decimal("5") and metrics["acos"]==Decimal("30")