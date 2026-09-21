from datetime import date,timedelta
from dataclasses import replace
import traceback
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

def test_historical_reads_paginate_preserve_decimals_and_isolate_scope():
 repo,resource=repository();table=repo.performance_table;table.page_size=2
 assert repo.count_performance_rows("s","m","p")==0
 assert repo.get_data_date_range("s","m","p")== (None,None)
 assert repo.list_window("s","m","p",7,date(2026,2,9))==[]
 end=date(2026,2,9);start=end-timedelta(days=6)
 rows=[replace(row(),date=day) for day in (start-timedelta(days=1),start,end,end+timedelta(days=1))]
 rows += [row(profile="other"),replace(row(),seller_id="other"),replace(row(),marketplace_id="other")]
 repo.save_many(rows)
 assert repo.count_performance_rows("s","m","p")==4
 assert repo.get_data_date_range("s","m","p")==("2026-02-02","2026-02-10")
 actual=repo.list_window("s","m","p",7,end)
 assert actual==[rows[1],rows[2]] and isinstance(actual[0].spend,Decimal)
 for scope in (("other","m","p"),("s","other","p"),("s","m","other")):
  assert repo.count_performance_rows(*scope)==1 and len(repo.list_window(*scope,7,end))==1
 assert any("ExclusiveStartKey" in call for call in table.query_calls)
 assert all(call["ConsistentRead"] and "scope_key = :scope" in call["KeyConditionExpression"] for call in table.query_calls)
 assert resource.client.calls and len(resource.client.calls)==1

def test_window_filters_are_combined_and_window_is_validated():
 repo,_=repository();match=replace(row(),keyword_id="k",search_term="term")
 repo.save_many([match,replace(match,campaign_id="other"),replace(match,keyword_id="other"),replace(match,search_term="other")])
 assert repo.list_window("s","m","p",7,date(2026,2,9),campaign_id="c",keyword_id="k",search_term="term")==[match]
 assert repo.list_window("s","m","p",7,date(2026,2,9),campaign_id="absent")==[]
 with pytest.raises(ValueError,match="Unsupported Ads query window"):repo.list_window("s","m","p",8)

@pytest.mark.parametrize("method",["count_performance_rows","get_data_date_range","list_window"])
def test_historical_query_failure_is_sanitized(monkeypatch,method):
 repo,_=repository()
 def unavailable(**kwargs):raise RuntimeError("sensitive-sentinel")
 monkeypatch.setattr(repo.performance_table,"query",unavailable)
 args=(7,date(2026,2,9)) if method=="list_window" else ()
 with pytest.raises(AdsDynamoDbRepositoryError) as error:getattr(repo,method)("s","m","p",*args)
 assert "sensitive-sentinel" not in "".join(traceback.format_exception(error.value))

@pytest.mark.parametrize("method,field,value",[("get_data_date_range","date","sensitive-sentinel"),("list_window","date","sensitive-sentinel"),("list_window","clicks","sensitive-sentinel"),("list_window","spend","Infinity")])
def test_historical_invalid_stored_values_are_sanitized(method,field,value):
 repo,resource=repository();repo.save_many([row()]);next(iter(resource.store["performance"].values()))[field]=value
 args=(7,date(2026,2,9)) if method=="list_window" else ()
 with pytest.raises(AdsDynamoDbRepositoryError) as error:getattr(repo,method)("s","m","p",*args)
 assert value not in "".join(traceback.format_exception(error.value))
