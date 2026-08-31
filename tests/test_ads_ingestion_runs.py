from datetime import date,datetime,timezone
from app.amazon_ads.ingestion_models import AdsIngestionResult
from app.database.ads_repository import AdsPerformanceRepository
def result(run_id,success=True,errors=()):
 now=datetime(2026,1,30,tzinfo=timezone.utc);return AdsIngestionResult(run_id,now,now,1,2,3,4,4,4,0,success,errors)
def test_ingestion_runs_persist_and_are_scope_isolated(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_ingestion_run(result("one"),"seller","market","profile");repo.save_ingestion_run(result("two",False,("source failed",)),"seller","market","profile")
 rows=repo.list_ingestion_runs("seller","market","profile");assert len(rows)==2 and repo.list_ingestion_runs("other","market","profile")==[] and "secret" not in str(rows)