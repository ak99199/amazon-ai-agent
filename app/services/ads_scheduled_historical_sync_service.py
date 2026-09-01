"""Disabled-by-default trusted scheduled historical-sync gate."""
from datetime import timedelta
from app.amazon_ads.sync_models import AdsScheduledHistoricalSyncResult
from app.services.ads_historical_sync_execution_service import HISTORICAL_SYNC_MODE
from app.services.ads_scheduled_sync_health_service import scheduled_next_due
from app.services.ads_sync_recovery_service import AdsSyncRecoveryService

class AdsScheduledHistoricalSyncService:
 def __init__(self,config,readiness_service,repository,execution_factory,now):self.config=config;self.readiness=readiness_service;self.repository=repository;self.execution_factory=execution_factory;self.now=now
 def run(self,seller_id,marketplace_id):
  if not self.config.enabled:return self._result("disabled",None,None,0,"Scheduled historical sync is disabled.")
  if not seller_id or not marketplace_id:return self._result("readiness_blocked",None,None,0,"Scheduled historical sync scope is unavailable.")
  ready=self.readiness.get()
  if not ready.manual_smoke_test_allowed:return self._result("readiness_blocked",None,None,0,"Scheduled historical sync is blocked by production readiness.")
  profile=str(self.readiness.settings.profile_id);now=self.now()
  recovery=AdsSyncRecoveryService(self.repository,self.config.stale_run_after_hours,self.now).reconcile(seller_id,marketplace_id,profile)
  if recovery.status=="unavailable":return self._result("unavailable",None,None,0,"Scheduled historical sync lock state is unavailable.","stale_recovery_error")
  if self.repository.active_sync_run(seller_id,marketplace_id,profile):return self._result("already_running",None,None,0,"A same-scope Ads sync is already running.")
  previous=self.repository.latest_successful_sync(seller_id,marketplace_id,profile,HISTORICAL_SYNC_MODE,"scheduled")
  if scheduled_next_due(previous,self.config.interval_hours) and scheduled_next_due(previous,self.config.interval_hours)>now:return self._result("not_due",None,None,0,"Scheduled historical sync is not due yet.")
  result=self.execution_factory().execute(seller_id,marketplace_id,profile,now.date()-timedelta(days=2),now.date()-timedelta(days=1),"scheduled")
  return AdsScheduledHistoricalSyncResult(result.status,result.run_id,result.started_at,result.completed_at,result.rows_persisted,"scheduled",result.message,result.error_code)
 def _result(self,status,run_id,started,rows,message,error=None,completed=None):return AdsScheduledHistoricalSyncResult(status,run_id,started,completed,rows,"scheduled",message,error)
