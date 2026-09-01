from datetime import date
from decimal import Decimal
import pytest
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.database.ads_repository import AdsPerformanceRepository

def row(seller="seller",market="market",profile="profile",day=date(2026,2,8),campaign="c1",spend="1.25"):
 return AdsPerformanceDaily(seller,market,profile,day,"SP",campaign_id=campaign,impressions=10,clicks=2,spend=Decimal(spend),orders=1,units=1,sales=Decimal("4.50"))
def listed(repo,seller="seller",market="market",profile="profile"):
 return repo.list_rows(seller,market,profile,date(2026,2,8),date(2026,2,9),today=date(2026,2,9))
def test_batch_upsert_preserves_scope_and_daily_campaign_grain(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_many([row(),row(day=date(2026,2,9)),row(campaign="c2"),row(seller="other"),row(market="other"),row(profile="other")])
 assert len(listed(repo))==3 and len(listed(repo,"other"))==1 and len(listed(repo,market="other"))==1 and len(listed(repo,profile="other"))==1
def test_identical_replay_is_idempotent_and_corrected_metrics_update(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_many([row()]);repo.save_many([row()]);assert len(listed(repo))==1
 repo.save_many([row(spend="9.99")]);items=listed(repo);assert len(items)==1 and items[0].spend==Decimal("9.99")
def test_batch_failure_rolls_back_all_rows(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db")
 invalid=row();object.__setattr__(invalid,"seller_id",None)
 with pytest.raises(Exception):repo.save_many([row(),invalid])
 assert repo.count_performance_rows("seller","market","profile")==0
