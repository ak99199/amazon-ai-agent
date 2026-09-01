"""Authenticated-call orchestration for one manual historical campaign report sync."""
from datetime import timedelta
from uuid import uuid4
from app.amazon_ads.sync_models import AdsManualHistoricalSyncResult,AdsManualSyncResult

HISTORICAL_SYNC_MODE="historical_campaign_report"
class AdsManualHistoricalSyncService:
 def __init__(self,readiness_service,gate_service,repository,persistence_service,now):self.readiness=readiness_service;self.gate=gate_service;self.repository=repository;self.persistence=persistence_service;self.now=now
 def run(self,seller_id,marketplace_id,confirm_live_read=False):
  if confirm_live_read is not True:return self._result("blocked_confirmation",None,None,0,False,"Explicit live-read confirmation is required.")
  ready=self.readiness.get()
  if not ready.manual_smoke_test_allowed:return self._result("blocked_readiness",None,None,0,False,"Historical sync is blocked by production readiness.")
  profile=str(self.readiness.settings.profile_id);today=self.now().date();start=today-timedelta(days=2);end=today-timedelta(days=1)
  gate=self.gate.evaluate(seller_id,marketplace_id,profile,start,end)
  if not gate.allowed:
   status="already_running" if gate.sync_in_progress else "cooldown_active" if gate.cooldown_active else "blocked_readiness"
   return self._result(status,None,None,0,False,gate.status_message)
  started=self.now();run_id=str(uuid4());starting=AdsManualSyncResult(run_id,HISTORICAL_SYNC_MODE,seller_id,marketplace_id,profile,start,end,started,None,False,"running")
  if not self.repository.start_sync_run_if_idle(starting,started-timedelta(minutes=30)):return self._result("already_running",None,None,0,False,"A historical Ads sync is already running.")
  try:result=self.persistence.run(True)
  except Exception:return self._finalize(starting,"failed",False,0,False,"unknown_error","Historical Ads sync failed safely.")
  if result.status in ("success","valid_empty"):return self._finalize(starting,"succeeded",True,result.rows_persisted,result.status=="valid_empty",None,"Historical Ads sync completed.")
  return self._finalize(starting,"failed",False,0,False,result.status,"Historical Ads sync did not complete.")
 def _finalize(self,starting,status,success,rows,empty,error,message):
  completed=self.now();run=AdsManualSyncResult(starting.sync_id,starting.mode,starting.seller_id,starting.marketplace_id,starting.profile_id,starting.start_date,starting.end_date,starting.started_at,completed,success,"completed" if success else "failed",report_rows_received=rows,rows_normalized=rows,rows_saved=rows,error_code=error,safe_error_message=None if success else message)
  try:self.repository.save_sync_run(run)
  except Exception:return self._result("failed",starting.sync_id,starting.started_at,0,False,"Historical Ads sync finalization failed.","run_finalization_error",completed)
  return self._result(status,starting.sync_id,starting.started_at,rows,empty,message,error,completed)
 def _result(self,status,run_id,started,rows,empty,message,error=None,completed=None):return AdsManualHistoricalSyncResult(status,run_id,started,completed,rows,empty,message,error)
