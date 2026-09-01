"""Shared atomic historical-sync run lifecycle for trusted callers."""
from datetime import timedelta
from uuid import uuid4
from app.amazon_ads.sync_models import AdsManualHistoricalSyncResult,AdsManualSyncResult

HISTORICAL_SYNC_MODE="historical_campaign_report"
class AdsHistoricalSyncExecutionService:
 def __init__(self,repository,persistence_service,now):self.repository=repository;self.persistence=persistence_service;self.now=now
 def execute(self,seller,marketplace,profile,start,end,trigger_source):
  started=self.now();run_id=str(uuid4());starting=AdsManualSyncResult(run_id,HISTORICAL_SYNC_MODE,seller,marketplace,profile,start,end,started,None,False,"running",trigger_source=trigger_source)
  if not self.repository.start_sync_run_if_idle(starting,started-timedelta(minutes=30)):return AdsManualHistoricalSyncResult("already_running",None,None,None,0,False,"A historical Ads sync is already running.")
  try:result=self.persistence.run(True)
  except Exception:return self._finalize(starting,"failed",False,0,False,"unknown_error","Historical Ads sync failed safely.")
  if result.status in ("success","valid_empty"):return self._finalize(starting,"succeeded",True,result.rows_persisted,result.status=="valid_empty",None,"Historical Ads sync completed.")
  return self._finalize(starting,"failed",False,0,False,result.status,"Historical Ads sync did not complete.")
 def _finalize(self,starting,status,success,rows,empty,error,message):
  completed=self.now();run=AdsManualSyncResult(starting.sync_id,starting.mode,starting.seller_id,starting.marketplace_id,starting.profile_id,starting.start_date,starting.end_date,starting.started_at,completed,success,"completed" if success else "failed",report_rows_received=rows,rows_normalized=rows,rows_saved=rows,error_code=error,safe_error_message=None if success else message,trigger_source=starting.trigger_source)
  try:self.repository.save_sync_run(run)
  except Exception:return AdsManualHistoricalSyncResult("failed",starting.sync_id,starting.started_at,completed,0,False,"Historical Ads sync finalization failed.","run_finalization_error")
  return AdsManualHistoricalSyncResult(status,starting.sync_id,starting.started_at,completed,rows,empty,message,error)
