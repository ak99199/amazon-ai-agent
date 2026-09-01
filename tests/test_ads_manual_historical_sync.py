from datetime import date,datetime,timedelta,timezone
import pytest
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_models import AdsHistoricalReportPersistenceResult
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.sync_models import AdsSyncGateResult
from app.services.ads_manual_historical_sync_service import AdsManualHistoricalSyncService,HISTORICAL_SYNC_MODE
from app.services.ads_production_readiness_service import AdsProductionReadinessService
NOW=datetime(2026,2,10,tzinfo=timezone.utc)
def readiness(approval="approved",settings=None,config=None):return AdsProductionReadinessService(settings or AdsSettings("id","secret","refresh","profile","FE"),config or AdsLiveReadConfig(True,False),approval)
class Gate:
 def __init__(self,allowed=True,active=False,cooldown=False):self.allowed=allowed;self.active=active;self.cooldown=cooldown;self.calls=[]
 def evaluate(self,*args):self.calls.append(args);return AdsSyncGateResult(self.allowed,"live" if self.allowed else None,"allowed_live" if self.allowed else "blocked", "allowed" if self.allowed else "blocked","approved",True,False,True,True,self.active,self.cooldown,date(2026,2,8),date(2026,2,9),2,())
class Repo:
 def __init__(self,start=True,save_error=False):self.start=start;self.save_error=save_error;self.started=[];self.saved=[]
 def start_sync_run_if_idle(self,run,not_before):self.started.append(run);return self.start
 def save_sync_run(self,run):
  if self.save_error:raise RuntimeError("raw SQL")
  self.saved.append(run);return run
class Persistence:
 def __init__(self,status="success",rows=2,error=None):self.status=status;self.rows=rows;self.error=error;self.calls=[]
 def run(self,confirm):
  self.calls.append(confirm)
  if self.error:raise self.error
  return AdsHistoricalReportPersistenceResult(self.status,NOW,NOW,"campaign","2026-02-08","2026-02-09",self.rows,self.rows,self.rows,(),(),"safe")
def service(ready=None,gate=None,repo=None,persistence=None):
 repo=repo or Repo();gate=gate or Gate();persistence=persistence or Persistence();return AdsManualHistoricalSyncService(ready or readiness(),gate,repo,persistence,lambda:NOW),repo,gate,persistence
def test_confirmation_false_creates_no_run_or_pipeline_call():
 svc,repo,gate,persistence=service();result=svc.run("seller","market",False);assert result.status=="blocked_confirmation" and repo.started==[] and gate.calls==[] and persistence.calls==[]
@pytest.mark.parametrize("ready",[readiness("pending"),readiness("rejected"),readiness(config=AdsLiveReadConfig(False,False)),readiness(config=AdsLiveReadConfig(True,True)),readiness(settings=AdsSettings(None,"secret","refresh","profile","FE")),readiness(settings=AdsSettings("id","secret","refresh",None,"FE")),readiness(settings=AdsSettings("id","secret","refresh","profile","XX"))])
def test_readiness_blocks_before_gate_run_or_pipeline(ready):
 svc,repo,gate,persistence=service(ready=ready);result=svc.run("seller","market",True);assert result.status=="blocked_readiness" and repo.started==[] and gate.calls==[] and persistence.calls==[]
@pytest.mark.parametrize("gate,expected",[(Gate(False,True,False),"already_running"),(Gate(False,False,True),"cooldown_active")])
def test_concurrency_and_cooldown_create_no_second_run(gate,expected):
 svc,repo,_,persistence=service(gate=gate);result=svc.run("seller","market",True);assert result.status==expected and repo.started==[] and persistence.calls==[]
def test_atomic_start_rejection_creates_no_report_or_persistence():
 svc,repo,_,persistence=service(repo=Repo(start=False));result=svc.run("seller","market",True);assert result.status=="already_running" and len(repo.started)==1 and persistence.calls==[]
def test_success_and_valid_empty_finalize_existing_run():
 for status,rows in (("success",2),("valid_empty",0)):
  svc,repo,_,_=service(persistence=Persistence(status,rows));result=svc.run("seller","market",True);assert result.status=="succeeded" and result.rows_persisted==rows and result.valid_empty==(status=="valid_empty") and len(repo.started)==1 and len(repo.saved)==1 and repo.saved[0].mode==HISTORICAL_SYNC_MODE and repo.saved[0].success
@pytest.mark.parametrize("status",["partial_valid","auth_error","rate_limited","remote_error","poll_timeout","download_error","persistence_error"])
def test_controlled_failures_finalize_run_as_failed(status):
 svc,repo,_,_=service(persistence=Persistence(status,0));result=svc.run("seller","market",True);assert result.status=="failed" and len(repo.saved)==1 and repo.saved[0].status=="failed" and repo.saved[0].error_code==status
def test_unexpected_failure_is_sanitized_and_finalized():
 svc,repo,_,_=service(persistence=Persistence(error=RuntimeError("signed URL Authorization")));result=svc.run("seller","market",True);assert result.status=="failed" and len(repo.saved)==1 and "signed" not in str(result.public_dict()) and "Authorization" not in str(result.public_dict())
