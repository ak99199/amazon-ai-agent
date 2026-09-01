from datetime import date,datetime,timedelta,timezone
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.sync_models import AdsManualSyncResult,AdsSyncGateResult
from app.services.ads_historical_sync_health_service import AdsHistoricalSyncHealthService
from app.services.ads_manual_historical_sync_service import HISTORICAL_SYNC_MODE
NOW=datetime(2026,2,10,12,tzinfo=timezone.utc)
def run(identifier,status="completed",success=True,started=NOW-timedelta(hours=1),profile="p",rows=2):return AdsManualSyncResult(identifier,HISTORICAL_SYNC_MODE,"s","m",profile,date(2026,2,8),date(2026,2,9),started,started+timedelta(minutes=1) if status not in ("running","starting") else None,success,status,rows_saved=rows,error_code=None if success else "safe_error")
class Repo:
 def __init__(self,runs=(),active=None,last_date=None,cooldown_success=None):self.runs=list(runs);self.active=active;self.last_date=last_date;self.cooldown_success=cooldown_success;self.calls=[]
 def list_sync_runs(self,s,m,p,limit,mode):self.calls.append((s,m,p,limit,mode));return [item for item in self.runs if item.profile_id==p][:limit]
 def active_sync_run(self,s,m,p):return self.active
 def latest_campaign_performance_date(self,s,m,p):return self.last_date
 def latest_successful_sync(self,s,m,p,mode=None):
  if mode:return next((item for item in self.runs if item.profile_id==p and item.success),None)
  return self.cooldown_success
class Gate:
 def __init__(self,cooldown=False,seconds=60):self.settings=AdsSettings("i","s","r","p","FE");self.cooldown_seconds=seconds;self.cooldown=cooldown;self.calls=[]
 def evaluate(self,*args):self.calls.append(args);return AdsSyncGateResult(not self.cooldown,"live","blocked_cooldown" if self.cooldown else "allowed_live","cooldown" if self.cooldown else "allowed","approved",True,False,True,True,False,self.cooldown,date(2026,2,8),date(2026,2,9),2,())
def health(repo,gate=None,stale=72):return AdsHistoricalSyncHealthService(repo,gate or Gate(),lambda:NOW,stale).get("s","m")
def test_no_run_running_healthy_failed_and_degraded_states():
 assert health(Repo()).overall_status=="no_sync_yet"
 assert health(Repo([run("active",status="running",success=False)],active={"sync_id":"active"})).overall_status=="running"
 assert health(Repo([run("ok")],last_date=date(2026,2,9))).overall_status=="healthy"
 assert health(Repo([run("bad",success=False,status="failed")])).overall_status=="failed"
 assert health(Repo([run("bad",success=False,status="failed"),run("ok",started=NOW-timedelta(hours=2))],last_date=date(2026,2,9))).overall_status=="degraded"
def test_freshness_uses_completed_day_and_stale_threshold():
 fresh=health(Repo([run("ok")],last_date=date(2026,2,9)),stale=24);stale=health(Repo([run("ok")],last_date=date(2026,2,5)),stale=24)
 assert fresh.data_freshness_status=="fresh" and fresh.data_age_seconds==12*3600 and stale.overall_status=="stale"
def test_cooldown_remaining_is_nonnegative_and_expiry_is_gate_authoritative():
 success=run("ok",started=NOW-timedelta(seconds=20));success=AdsManualSyncResult(**{**success.__dict__,"finished_at":NOW-timedelta(seconds=10)})
 current=health(Repo([success],last_date=date(2026,2,9),cooldown_success=success),Gate(True,60));expired=health(Repo([success],last_date=date(2026,2,9)),Gate(False,60))
 assert current.overall_status=="cooldown" and current.cooldown_remaining_seconds==50 and expired.overall_status=="healthy"
def test_history_is_bounded_safe_latest_order_and_profile_isolated():
 rows=[run(f"r{i}",started=NOW-timedelta(minutes=i)) for i in range(15)]+[run("other",profile="other")];repo=Repo(rows,last_date=date(2026,2,9));result=health(repo)
 assert len(result.recent_runs)==10 and [item["run_id"] for item in result.recent_runs[:2]]==["r0","r1"] and "other" not in str(result.public_dict()) and repo.calls[0][-1]==HISTORICAL_SYNC_MODE
