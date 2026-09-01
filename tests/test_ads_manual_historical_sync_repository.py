from datetime import date,datetime,timedelta,timezone
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_manual_historical_sync_service import HISTORICAL_SYNC_MODE
from app.services.ads_sync_gate_service import AdsSyncGateService
NOW=datetime(2026,2,10,tzinfo=timezone.utc)
def run(identifier,seller="s",profile="p",status="running",success=False,started=NOW,mode=HISTORICAL_SYNC_MODE):return AdsManualSyncResult(identifier,mode,seller,"m",profile,date(2026,2,8),date(2026,2,9),started,started if status not in ("running","starting") else None,success,status)
def test_atomic_start_blocks_same_scope_but_not_different_profile(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");assert repo.start_sync_run_if_idle(run("one"),NOW-timedelta(minutes=30));assert not repo.start_sync_run_if_idle(run("two"),NOW-timedelta(minutes=30));assert repo.start_sync_run_if_idle(run("other",profile="other"),NOW-timedelta(minutes=30))
def test_history_is_mode_filtered_scoped_bounded_and_latest_first(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_sync_run(run("old",status="completed",success=True,started=NOW-timedelta(minutes=2)));repo.save_sync_run(run("new",status="failed",started=NOW-timedelta(minutes=1)));repo.save_sync_run(run("general",status="completed",success=True,mode="live"));repo.save_sync_run(run("other",seller="other",status="completed",success=True))
 assert [item.sync_id for item in repo.list_sync_runs("s","m","p",1,HISTORICAL_SYNC_MODE)]==["new"]
def test_cooldown_anchors_success_only_and_expires(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_sync_run(run("failed",status="failed",started=NOW-timedelta(seconds=10)));gate=AdsSyncGateService(AdsSettings("i","s","r","p","FE"),repo,AdsLiveReadConfig(True,False),"approved",lambda:NOW,cooldown_seconds=60);assert gate.evaluate("s","m",start_date=date(2026,2,8),end_date=date(2026,2,9)).allowed
 repo.save_sync_run(run("success",status="completed",success=True,started=NOW-timedelta(seconds=10)));assert gate.evaluate("s","m",start_date=date(2026,2,8),end_date=date(2026,2,9)).status_code=="blocked_cooldown"
 expired=AdsSyncGateService(AdsSettings("i","s","r","p","FE"),repo,AdsLiveReadConfig(True,False),"approved",lambda:NOW+timedelta(seconds=61),cooldown_seconds=60);assert expired.evaluate("s","m",start_date=date(2026,2,8),end_date=date(2026,2,9)).allowed
