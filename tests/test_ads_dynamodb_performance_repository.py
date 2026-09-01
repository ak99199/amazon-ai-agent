from datetime import date
from decimal import Decimal
import pytest
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.database.ads_dynamodb_repository import AdsDynamoDbRepositoryError,DynamoDbAdsHistoricalRepository
from tests.ads_dynamodb_fakes import Resource

def row(clicks=2,profile="p",campaign="c"):
 return AdsPerformanceDaily("s","m",profile,date(2026,2,9),"SP",campaign,"Campaign",impressions=10,clicks=clicks,spend=Decimal("1.23"),orders=1,units=1,sales=Decimal("4.56"))
def repository():
 resource=Resource();return DynamoDbAdsHistoricalRepository(resource.Table("performance"),resource.Table("runs"),resource.client),resource

def test_performance_replay_and_correction_use_one_decimal_safe_item():
 repo,resource=repository();repo.save_many([row()]);repo.save_many([row(7)])
 assert len(resource.store["performance"])==1
 saved=next(iter(resource.store["performance"].values()));assert saved["clicks"]==7 and saved["spend"]==Decimal("1.23") and saved["sales"]==Decimal("4.56")
 assert repo.latest_campaign_performance_date("s","m","p")==date(2026,2,9) and repo.latest_campaign_performance_date("s","m","other") is None

def test_empty_duplicate_and_transaction_failure_are_all_or_nothing():
 repo,resource=repository();assert repo.save_many([])==[] and resource.client.calls==[]
 with pytest.raises(AdsDynamoDbRepositoryError):repo.save_many([row(),row()])
 resource.client.fail=True
 with pytest.raises(AdsDynamoDbRepositoryError):repo.save_many([row(),row(profile="other")])
 assert resource.store["performance"]=={}
