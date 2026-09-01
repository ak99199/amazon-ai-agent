from datetime import date,datetime,timedelta,timezone
from app.amazon_ads.config import AdsScheduledSyncConfig,AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.services.ads_production_readiness_service import AdsProductionReadinessService
from app.services.ads_scheduled_sync_health_service import AdsScheduledSyncHealthService

NOW=datetime(2026,2,10,12,tzinfo=timezone.utc)
def run(identifier,started,success,status="completed",trigger="scheduled",profile="p",error=None):
 return AdsManualSyncResult(identifier,"historical_campaign_report","s","m",profile,date(2026,2,8),date(2026,2,9),started,started+timedelta(minutes=1) if status!="running" else None,success,status,error_code=error,trigger_source=trigger)
class Repo:
 def __init__(self,runs=(),active=None):self.runs=list(runs);self.active=active;self.writes=0
 def list_sync_runs(self,s,m,p,limit,mode):return [r for r in self.runs if r.profile_id==p and r.mode==mode][:limit]
 def latest_successful_sync(self,s,m,p,mode,trigger):return next((r for r in self.runs if r.profile_id==p and r.mode==mode and r.trigger_source==trigger and r.success),None)
 def latest_failed_sync(self,s,m,p,mode,trigger):return next((r for r in self.runs if r.profile_id==p and r.mode==mode and r.trigger_source==trigger and r.status=="failed"),None)
 def active_sync_run(self,*scope):return self.active
 def finalize_stale_sync_run(self,*args):self.writes+=1;return True
def readiness(ready=True):return AdsProductionReadinessService(AdsSettings("id","secret","refresh","p","FE"),AdsLiveReadConfig(ready,False),"approved")
def health(repo,enabled=True,ready=True):return AdsScheduledSyncHealthService(AdsScheduledSyncConfig(enabled,24,6),readiness(ready),repo,lambda:NOW).get("s","m")

def test_disabled_and_no_history_states_are_deterministic():
 assert health(Repo(),False).status=="disabled"
 due=health(Repo());assert due.status=="due" and due.next_due_at is None and not due.overdue

def test_next_due_overdue_and_failure_streak_ignore_manual_attempts():
 success=run("success",NOW-timedelta(hours=30),True);manual=run("manual",NOW-timedelta(hours=3),False,"failed","manual",error="remote_error");bad2=run("bad2",NOW-timedelta(hours=1),False,"failed",error="report_failed");bad1=run("bad1",NOW-timedelta(hours=2),False,"failed",error="remote_error")
 result=health(Repo([bad2,manual,bad1,success]))
 assert result.status=="degraded" and result.consecutive_failures==2 and result.overdue and result.last_failure["run_id"]=="bad2"

def test_success_resets_streak_and_valid_empty_is_success():
 success=run("empty",NOW-timedelta(hours=1),True);older=run("bad",NOW-timedelta(hours=2),False,"failed",error="remote_error")
 result=health(Repo([success,older]));assert result.consecutive_failures==0 and result.status=="not_due" and result.last_success_at

def test_stale_health_is_read_only_and_profile_isolated():
 stale=run("stale",NOW-timedelta(hours=6),False,"running");other=run("other",NOW-timedelta(days=2),False,"failed",profile="other",error="remote_error");repo=Repo([other,stale],stale)
 result=health(repo)
 assert result.status=="stale_run" and result.active_run_stale and repo.writes==0 and "other" not in str(result.public_dict())

def test_readiness_blocked_remains_distinct():
 assert health(Repo(),ready=False).status=="readiness_blocked"

def test_stale_config_falls_back_safely(monkeypatch):
 for value in ("0","-1","NaN","999"):
  monkeypatch.setenv("AMAZON_ADS_SYNC_STALE_RUN_AFTER_HOURS",value);assert AdsScheduledSyncConfig.from_environment().stale_run_after_hours==6
