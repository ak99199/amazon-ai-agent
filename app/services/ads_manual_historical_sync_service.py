"""Authenticated-call orchestration for one manual historical campaign report sync."""
from datetime import timedelta
from app.amazon_ads.sync_models import AdsManualHistoricalSyncResult
from app.services.ads_historical_sync_execution_service import AdsHistoricalSyncExecutionService,HISTORICAL_SYNC_MODE

class AdsManualHistoricalSyncService:
 def __init__(self,readiness_service,gate_service,repository,persistence_service,now,recovery_service=None,dependency_factory=None,mode=HISTORICAL_SYNC_MODE,trigger_source="manual",download=True,persist=True):
  self.readiness=readiness_service;self.gate=gate_service;self.repository=repository;self.now=now;self.recovery=recovery_service;self.mode=mode;self.trigger_source=trigger_source;self.download=download;self.persist=persist;self.execution=AdsHistoricalSyncExecutionService(repository,persistence_service,now,dependency_factory)
 def run(self,seller_id,marketplace_id,confirm_live_read=False):
  if confirm_live_read is not True:return self._result("blocked_confirmation",None,None,0,False,"Explicit live-read confirmation is required.")
  ready=self.readiness.get()
  if not ready.manual_smoke_test_allowed:return self._result("blocked_readiness",None,None,0,False,"Historical sync is blocked by production readiness.")
  profile=str(self.readiness.settings.profile_id);today=self.now().date();start=today-timedelta(days=2);end=today-timedelta(days=1)
  if self.recovery:
   recovery=self.recovery.reconcile(seller_id,marketplace_id,profile)
   if recovery.status=="unavailable":return self._result("unavailable",None,None,0,False,"Historical Ads sync lock state is unavailable.","stale_recovery_error")
   if recovery.status=="recovered":return self._result("stale_recovered",None,None,0,False,"A stale Ads report run was safely recovered; retry to start a new report.")
  active=self.repository.active_sync_run(seller_id,marketplace_id,profile)
  if active:
   if active.mode!=self.mode:return self._result("already_running",active.sync_id,active.started_at,0,False,"A same-scope Ads report is already running.")
   return self.execution.resume(active,self.download,self.persist)
  gate=self.gate.evaluate(seller_id,marketplace_id,profile,start,end,7,self.mode)
  if not gate.allowed:
   status="already_running" if gate.sync_in_progress else "cooldown_active" if gate.cooldown_active else "blocked_readiness"
   return self._result(status,None,None,0,False,gate.status_message)
  return self.execution.start(seller_id,marketplace_id,profile,start,end,self.mode,self.trigger_source)
 def _result(self,status,run_id,started,rows,empty,message,error=None,completed=None):return AdsManualHistoricalSyncResult(status,run_id,started,completed,rows,empty,message,error)
