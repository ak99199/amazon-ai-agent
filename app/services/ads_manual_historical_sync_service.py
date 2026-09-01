"""Authenticated-call orchestration for one manual historical campaign report sync."""
from datetime import timedelta
from app.amazon_ads.sync_models import AdsManualHistoricalSyncResult
from app.services.ads_historical_sync_execution_service import AdsHistoricalSyncExecutionService,HISTORICAL_SYNC_MODE

class AdsManualHistoricalSyncService:
 def __init__(self,readiness_service,gate_service,repository,persistence_service,now):self.readiness=readiness_service;self.gate=gate_service;self.repository=repository;self.persistence=persistence_service;self.now=now;self.execution=AdsHistoricalSyncExecutionService(repository,persistence_service,now)
 def run(self,seller_id,marketplace_id,confirm_live_read=False):
  if confirm_live_read is not True:return self._result("blocked_confirmation",None,None,0,False,"Explicit live-read confirmation is required.")
  ready=self.readiness.get()
  if not ready.manual_smoke_test_allowed:return self._result("blocked_readiness",None,None,0,False,"Historical sync is blocked by production readiness.")
  profile=str(self.readiness.settings.profile_id);today=self.now().date();start=today-timedelta(days=2);end=today-timedelta(days=1)
  gate=self.gate.evaluate(seller_id,marketplace_id,profile,start,end)
  if not gate.allowed:
   status="already_running" if gate.sync_in_progress else "cooldown_active" if gate.cooldown_active else "blocked_readiness"
   return self._result(status,None,None,0,False,gate.status_message)
  return self.execution.execute(seller_id,marketplace_id,profile,start,end,"manual")
 def _result(self,status,run_id,started,rows,empty,message,error=None,completed=None):return AdsManualHistoricalSyncResult(status,run_id,started,completed,rows,empty,message,error)
