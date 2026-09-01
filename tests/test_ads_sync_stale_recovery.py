from datetime import date,datetime,timedelta,timezone
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_sync_recovery_service import AdsSyncRecoveryService

NOW=datetime(2026,2,10,12,tzinfo=timezone.utc)
def run(identifier,started,status="running",seller="s",market="m",profile="p"):
 return AdsManualSyncResult(identifier,"historical_campaign_report",seller,market,profile,date(2026,2,8),date(2026,2,9),started,None,status!="running",status,trigger_source="scheduled")

def test_stale_cutoff_is_atomic_scope_aware_and_idempotent(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_sync_run(run("stale",NOW-timedelta(hours=6)))
 service=AdsSyncRecoveryService(repo,6,lambda:NOW)
 assert service.reconcile("s","m","p").status=="recovered"
 recovered=repo.list_sync_runs("s","m","p")[0]
 assert recovered.status=="failed" and recovered.error_code=="stale_run_timeout" and recovered.finished_at==NOW
 assert service.reconcile("s","m","p").status=="clear"

def test_fresh_and_other_scope_runs_are_never_recovered(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_sync_run(run("fresh",NOW-timedelta(hours=5,minutes=59)));repo.save_sync_run(run("other",NOW-timedelta(days=1),profile="other"))
 service=AdsSyncRecoveryService(repo,6,lambda:NOW)
 assert service.reconcile("s","m","p").status=="active"
 assert repo.list_sync_runs("s","m","p")[0].status=="running" and repo.list_sync_runs("s","m","other")[0].status=="running"

def test_terminal_rows_do_not_match_atomic_recovery(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");terminal=run("done",NOW-timedelta(days=1),"completed");repo.save_sync_run(terminal)
 assert not repo.finalize_stale_sync_run("done","s","m","p",NOW-timedelta(hours=6),NOW)
 assert repo.list_sync_runs("s","m","p")[0].status=="completed"

def test_repository_failure_is_sanitized():
 class Repo:
  def active_sync_run(self,*args):raise RuntimeError("database path and secret")
 result=AdsSyncRecoveryService(Repo(),6,lambda:NOW).reconcile("s","m","p")
 assert result.status=="unavailable" and "secret" not in str(result)
