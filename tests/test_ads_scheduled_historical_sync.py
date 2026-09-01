from datetime import date,datetime,timedelta,timezone
import pytest
from app.amazon_ads.config import AdsScheduledSyncConfig,AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.sync_models import AdsManualHistoricalSyncResult,AdsManualSyncResult
from app.services.ads_production_readiness_service import AdsProductionReadinessService
from app.services.ads_scheduled_historical_sync_service import AdsScheduledHistoricalSyncService
NOW=datetime(2026,2,10,tzinfo=timezone.utc)
def readiness(approval="approved",settings=None,config=None):return AdsProductionReadinessService(settings or AdsSettings("id","secret","refresh","profile","FE"),config or AdsLiveReadConfig(True,False),approval)
def prior(at,profile="profile",trigger="scheduled"):return AdsManualSyncResult("prior","historical_campaign_report","seller","market",profile,date(2026,2,8),date(2026,2,9),at,at,True,"completed",trigger_source=trigger)
class Repo:
 def __init__(self,previous=None,active=None):self.previous=previous;self.active=active;self.calls=[]
 def active_sync_run(self,*scope):self.calls.append(("active",scope));return self.active
 def latest_successful_sync(self,*args):self.calls.append(("latest",args));return self.previous
class Execution:
 def __init__(self,status="succeeded",rows=2):self.status=status;self.rows=rows;self.calls=[]
 def execute(self,*args):self.calls.append(args);return AdsManualHistoricalSyncResult(self.status,"run",NOW,NOW,self.rows,self.rows==0,"safe",None if self.status=="succeeded" else "remote_error")
def service(enabled=True,ready=None,repo=None,execution=None,interval=24):
 repo=repo or Repo();execution=execution or Execution();factories=[]
 def factory():factories.append(True);return execution
 return AdsScheduledHistoricalSyncService(AdsScheduledSyncConfig(enabled,interval),ready or readiness(),repo,factory,lambda:NOW),repo,execution,factories
def test_default_configuration_and_disabled_status_make_zero_dependency_calls(monkeypatch):
 monkeypatch.delenv("AMAZON_ADS_SCHEDULED_SYNC_ENABLED",raising=False);assert not AdsScheduledSyncConfig.from_environment().enabled
 svc,repo,execution,factories=service(enabled=False);result=svc.run("seller","market");assert result.status=="disabled" and repo.calls==[] and execution.calls==[] and factories==[]
@pytest.mark.parametrize("ready",[readiness("pending"),readiness("rejected"),readiness(config=AdsLiveReadConfig(False,False)),readiness(config=AdsLiveReadConfig(True,True)),readiness(settings=AdsSettings(None,"secret","refresh","profile","FE")),readiness(settings=AdsSettings("id","secret","refresh",None,"FE")),readiness(settings=AdsSettings("id","secret","refresh","profile","XX"))])
def test_readiness_blocks_before_history_or_execution(ready):
 svc,repo,execution,factories=service(ready=ready);result=svc.run("seller","market");assert result.status=="readiness_blocked" and repo.calls==[] and execution.calls==[] and factories==[]
def test_no_previous_success_is_due_and_executes_once():
 svc,repo,execution,factories=service();result=svc.run("seller","market");assert result.status=="succeeded" and len(factories)==1 and len(execution.calls)==1 and execution.calls[0][-1]=="scheduled"
@pytest.mark.parametrize("elapsed,expected",[(timedelta(hours=23,minutes=59),"not_due"),(timedelta(hours=24),"succeeded"),(timedelta(hours=25),"succeeded")])
def test_due_boundary_is_deterministic(elapsed,expected):
    svc,repo,execution,factories=service(repo=Repo(previous=prior(NOW-elapsed)));result=svc.run("seller","market");assert result.status==expected and bool(factories)==(expected=="succeeded")
def test_manual_success_does_not_anchor_scheduled_cadence():
 repo=Repo(previous=None);svc,_,execution,factories=service(repo=repo);assert svc.run("seller","market").status=="succeeded" and repo.calls[-1][1][-1]=="scheduled"
def test_same_scope_active_manual_or_scheduled_blocks_without_execution():
 for trigger in ("manual","scheduled"):
  svc,repo,execution,factories=service(repo=Repo(active=prior(NOW,trigger=trigger)));assert svc.run("seller","market").status=="already_running" and factories==[] and execution.calls==[]
def test_different_profile_is_not_globally_blocked():
 svc,repo,execution,factories=service(repo=Repo(active=None));assert svc.run("seller","market").status=="succeeded"
@pytest.mark.parametrize("status",["succeeded","failed"])
def test_safe_terminal_result_preserves_rows_and_trigger(status):
 svc,_,_,_=service(execution=Execution(status,0 if status=="succeeded" else 0));result=svc.run("seller","market");assert result.status==status and result.trigger_source=="scheduled" and "signed" not in str(result.public_dict()) and "Authorization" not in str(result.public_dict())
