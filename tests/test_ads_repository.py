from datetime import date
from decimal import Decimal
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.database.ads_repository import AdsPerformanceRepository

def row(day=date(2026,1,10),seller="seller",profile="profile",campaign="c1",keyword=None,term=None,spend="1.50"):
    return AdsPerformanceDaily(seller,"market",profile,day,"SP",campaign_id=campaign,keyword_id=keyword,search_term=term,impressions=10,clicks=2,spend=Decimal(spend),orders=1,units=1,sales=Decimal("10"))
def test_sqlite_initialization_and_deterministic_upsert(tmp_path):
    repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save(row());repo.save(row(spend="2.50"));rows=repo.list_rows("seller","market","profile",date(2026,1,10),date(2026,1,10),today=date(2026,1,10))
    assert len(rows)==1 and rows[0].spend==Decimal("2.50")
def test_scope_and_dimension_filters(tmp_path):
    repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_many([row(keyword="k1",term="term one"),row(day=date(2026,1,11),campaign="c2",keyword="k2",term="term two"),row(seller="other")])
    assert len(repo.list_rows("seller","market","profile",date(2026,1,10),date(2026,1,11),campaign_id="c2",today=date(2026,1,11)))==1
    assert len(repo.list_rows("seller","market","profile",date(2026,1,10),date(2026,1,11),keyword_id="k1",search_term="term one",today=date(2026,1,11)))==1
def test_windows_are_deterministic(tmp_path):
    repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_many([row(day=date(2026,1,1)),row(day=date(2026,1,23)),row(day=date(2026,1,30))])
    assert len(repo.list_window("seller","market","profile",7,date(2026,1,30)))==1
    assert len(repo.list_window("seller","market","profile",30,date(2026,1,30)))==3
    assert len(repo.list_window("seller","market","profile",90,date(2026,1,30)))==3
def test_seven_day_window_includes_exact_start_boundary(tmp_path):
    repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_many([row(day=date(2026,1,23)),row(day=date(2026,1,24)),row(day=date(2026,1,30))])
    rows=repo.list_window("seller","market","profile",7,date(2026,1,30))
    assert [item.date for item in rows]==[date(2026,1,24),date(2026,1,30)]