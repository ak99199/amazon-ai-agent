from datetime import date,datetime,timezone
from decimal import Decimal
import pytest
from app.amazon_ads.live_models import AdsLiveReportDownloadValidationResult
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_live_report_persistence_service import AdsLiveReportPersistenceService

NOW=datetime(2026,2,10,tzinfo=timezone.utc)
def row(seller="seller",market="market",profile="profile",day=date(2026,2,8),campaign="c1",spend="1.25"):return AdsPerformanceDaily(seller,market,profile,day,"SP",campaign_id=campaign,impressions=10,clicks=2,spend=Decimal(spend),orders=1,units=1,sales=Decimal("4.50"))
def diagnostic(status="success",validated=1,truncated=False):return AdsLiveReportDownloadValidationResult(status,NOW,NOW,"ready","campaign","2026-02-08","2026-02-09",True,1,"completed",True,True,True,True,True,validated,validated,validated if status=="success" else 0,0 if status=="success" else validated,truncated,(),(),"safe")
class Download:
 def __init__(self,status="success",rows=None):self.status=status;self.rows=[row()] if rows is None else rows;self.calls=[];self.lifecycle=type("Lifecycle",(),{"now":lambda self:NOW,"readiness_service":type("Readiness",(),{"settings":type("Settings",(),{"profile_id":"profile"})()})()})()
 def run_with_validated(self,confirm,seller,market,on_validated):
  self.calls.append((confirm,seller,market));result=diagnostic(self.status,len(self.rows))
  if confirm is not True:return diagnostic("blocked_confirmation",0)
  return on_validated(tuple(self.rows),result) if self.status in ("success","valid_empty") else result

def test_fully_valid_rows_persist_with_authoritative_scope(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");download=Download(rows=[row(seller="untrusted",market="untrusted",profile="untrusted"),row(seller="untrusted",market="untrusted",profile="untrusted",day=date(2026,2,9))]);result=AdsLiveReportPersistenceService(download,repo,"seller","market").run(True)
 assert result.status=="success" and result.rows_persisted==2 and repo.count_performance_rows("seller","market","profile")==2 and download.calls==[(True,"seller","market")]
def test_valid_empty_writes_zero_rows(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");result=AdsLiveReportPersistenceService(Download("valid_empty",[]),repo,"seller","market").run(True);assert result.status=="valid_empty" and result.rows_attempted==0 and repo.count_performance_rows("seller","market","profile")==0
@pytest.mark.parametrize("status",["partial_valid","validation_error","parse_error","decompression_error","download_error","poll_timeout","report_failed","auth_error","remote_error","rate_limited","blocked_readiness"])
def test_nonfully_valid_results_write_zero_rows(tmp_path,status):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");result=AdsLiveReportPersistenceService(Download(status),repo,"seller","market").run(True);assert result.status==status and result.rows_persisted==0 and repo.count_performance_rows("seller","market","profile")==0
def test_missing_confirmation_writes_zero_rows(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");result=AdsLiveReportPersistenceService(Download(),repo,"seller","market").run(False);assert result.status=="blocked_confirmation" and repo.count_performance_rows("seller","market","profile")==0
def test_truncated_success_is_not_a_fully_valid_batch_and_writes_zero_rows(tmp_path):
 class Truncated(Download):
  def run_with_validated(self,confirm,seller,market,on_validated):return on_validated(tuple(self.rows),diagnostic("success",1,True))
 repo=AdsPerformanceRepository(tmp_path/"ads.db");result=AdsLiveReportPersistenceService(Truncated(),repo,"seller","market").run(True);assert result.status=="validation_error" and repo.count_performance_rows("seller","market","profile")==0
def test_repository_failure_is_safe_and_leaks_no_details():
 class Broken:
  def save_many(self,rows):raise RuntimeError("SQL /secret/path")
 result=AdsLiveReportPersistenceService(Download(),Broken(),"seller","market").run(True);assert result.status=="persistence_error" and result.rows_persisted==0 and "SQL" not in str(result.public_dict()) and "secret" not in str(result.public_dict())
