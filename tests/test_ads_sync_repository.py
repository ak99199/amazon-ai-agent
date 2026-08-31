from datetime import datetime, timezone, date
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.database.ads_repository import AdsPerformanceRepository

def test_sync_repository_is_scoped_and_lists_runs(tmp_path):
 repository=AdsPerformanceRepository(tmp_path/"ads.db");run=AdsManualSyncResult("id","mock","seller","market","profile",date(2026,1,1),date(2026,1,1),datetime(2026,1,1,tzinfo=timezone.utc),datetime(2026,1,1,tzinfo=timezone.utc),True,"completed",rows_saved=1)
 repository.save_sync_run(run)
 assert repository.latest_sync_run("seller","market","profile")["sync_id"]=="id"
 assert len(repository.list_sync_runs("seller","market","profile"))==1
 assert repository.list_sync_runs("other","market","profile")==[]
