from datetime import date,datetime,timezone
from app.amazon_ads.search_terms import SearchTermReportService
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_ingestion_service import AdsIngestionService
class Campaigns:
 def list_campaigns(self,*a):return [object()]
class Keywords:
 def list_keywords(self,*a):return [object()]
 def list_targets(self,*a):return [object()]
class Source:
 def __init__(self,rows):self.rows=rows
 def list_search_terms(self,*a):return self.rows
def raw(**x):return {"date":"2026-01-10","campaignId":"c","impressions":1,"clicks":1,"cost":"1","purchases14d":1,"unitsSold14d":1,"sales14d":"2"}|x
def service(tmp_path):return AdsIngestionService(Campaigns(),Keywords(),SearchTermReportService(),AdsPerformanceRepository(tmp_path/"ads.db"),now=lambda:datetime(2026,1,30,tzinfo=timezone.utc))
def test_full_run_is_idempotent_and_rows_are_isolated(tmp_path):
 value=service(tmp_path);source=Source([raw()]);first=value.run("seller","market","profile",date(2026,1,10),date(2026,1,10),source,today=date(2026,1,30));second=value.run("seller","market","profile",date(2026,1,10),date(2026,1,10),source,today=date(2026,1,30));repo=value._repository
 assert first.success and first.rows_saved==1 and second.rows_saved==1 and len(repo.list_rows("seller","market","profile",date(2026,1,10),date(2026,1,10),today=date(2026,1,30)))==1 and repo.list_rows("seller","market","other",date(2026,1,10),date(2026,1,10),today=date(2026,1,30))==[]
def test_bad_row_is_isolated_and_source_failure_is_safe(tmp_path):
 value=service(tmp_path);result=value.run("seller","market","profile",date(2026,1,10),date(2026,1,10),Source([raw(),raw(cost="bad")]),today=date(2026,1,30));assert result.success and result.rows_saved==1 and result.rows_failed==1 and "bad" not in str(result.errors)
 class Broken:
  def list_search_terms(self,*a):raise RuntimeError("secret")
 failed=value.run("seller","market","profile",date(2026,1,10),date(2026,1,10),Broken(),today=date(2026,1,30));assert not failed.success and "secret" not in str(failed.errors)
def test_range_and_limits_are_bounded(tmp_path):
 value=service(tmp_path);source=Source([])
 for start,end in ((date(2026,1,11),date(2026,1,10)),(date(2026,1,1),date(2026,4,1))):
  try:value.run("s","m","p",start,end,source,today=date(2026,1,30));assert False
  except ValueError:pass