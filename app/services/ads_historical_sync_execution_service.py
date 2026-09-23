"""Shared atomic historical-sync run lifecycle for trusted callers."""
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.report_transport import AdsReportTransportError
from app.amazon_ads.sync_models import AdsManualHistoricalSyncResult,AdsManualSyncResult
from app.services.ads_live_report_lifecycle_validation_service import AdsLiveReportLifecycleValidationService

HISTORICAL_SYNC_MODE="historical_campaign_report"
VALIDATION_SYNC_MODE="historical_report_validation"

class AdsHistoricalSyncExecutionService:
 def __init__(self,repository,persistence_service,now,dependency_factory=None):
  self.repository=repository;self.persistence=persistence_service;self.now=now;self.dependencies=dependency_factory
 def execute(self,seller,marketplace,profile,start,end,trigger_source):
  started=self.now();starting=AdsManualSyncResult(str(uuid4()),HISTORICAL_SYNC_MODE,seller,marketplace,profile,start,end,started,None,False,"running",trigger_source=trigger_source)
  if not self.repository.start_sync_run_if_idle(starting,started-timedelta(minutes=30)):return self._result("already_running",None,"A historical Ads sync is already running.")
  try:result=self.persistence.run(True)
  except Exception:return self._finalize(starting,"failed",False,0,0,False,"unknown_error","Historical Ads sync failed safely.")
  if result.status in ("success","valid_empty"):return self._finalize(starting,"succeeded",True,result.rows_persisted,result.rows_persisted,result.status=="valid_empty",None,"Historical Ads sync completed.")
  return self._finalize(starting,"failed",False,0,0,False,result.status,"Historical Ads sync did not complete.")
 def start(self,seller,marketplace,profile,start,end,mode,trigger_source):
  started=self.now();starting=AdsManualSyncResult(str(uuid4()),mode,seller,marketplace,profile,start,end,started,None,False,"running",trigger_source=trigger_source,amazon_report_status="creating")
  if not self.repository.start_sync_run_if_idle(starting,started-timedelta(minutes=30)):return self._result("already_running",None,"A same-scope Ads report is already running.")
  try:
   transport,reporting=self.dependencies();request=reporting.build_request("campaign",start,end)
   definition=AdsLiveReportLifecycleValidationService._definition(request,started.date())
   report_id=transport.create(str(profile),definition)
  except (TypeError,ValueError,AdsReportTransportError):return self._finalize(starting,"failed",False,0,0,False,"validation_error","Historical Ads report creation failed.")
  except AdsApiClientError as error:return self._finalize(starting,"failed",False,0,0,False,self._api_status(error),"Historical Ads report creation failed.")
  except Exception:return self._finalize(starting,"failed",False,0,0,False,"remote_error","Historical Ads report creation failed.")
  created=replace(starting,report_id=report_id,report_type_id="spCampaigns",amazon_report_status="pending",report_created_at=self.now())
  try:saved=self.repository.save_created_report(created)
  except Exception:saved=False
  if not saved:return self._result("creating_unconfirmed",starting,"Historical Ads report state could not be confirmed; stale recovery is required.","report_state_error")
  return self._result("pending",created,"Historical Ads report was created and saved for a later status check.")
 def resume(self,run,download=False,persist=False):
  if not run.report_id:return self._result("creating_unconfirmed",run,"Historical Ads report creation is unconfirmed; stale recovery is required.","report_state_unconfirmed")
  claim=str(uuid4());checked_at=self.now()
  try:claimed=self.repository.claim_report_check(run.seller_id,run.marketplace_id,run.profile_id,run.sync_id,claim,checked_at)
  except Exception:return self._result("unavailable",run,"Historical Ads report state is unavailable.","report_claim_error")
  if not claimed:return self._result("already_processing",run,"Historical Ads report continuation is already being processed.")
  try:
   transport,_=self.dependencies();report_status=transport.status(str(claimed.profile_id),claimed.report_id)
  except AdsApiClientError as error:
   self._release(claimed,claim)
   return self._result("unavailable",claimed,"Historical Ads report status is unavailable.",self._api_status(error))
  except Exception:
   self._release(claimed,claim)
   return self._result("unavailable",claimed,"Historical Ads report status is unavailable.","remote_error")
  checked=replace(claimed,amazon_report_status=report_status.status,report_last_checked_at=self.now())
  if report_status.status in ("pending","processing"):
   if not self.repository.save_report_check(checked,claim):return self._result("already_processing",checked,"Historical Ads report state changed concurrently.")
   return self._result("pending",checked,"Historical Ads report is still processing.")
  if report_status.status=="completed" and not download:
   if not self.repository.save_report_check(checked,claim):return self._result("already_processing",checked,"Historical Ads report state changed concurrently.")
   return self._result("download_ready",checked,"Historical Ads report is ready for bounded download validation.")
  if report_status.status=="completed":
   try:result=self.persistence.complete(transport,checked,report_status) if persist else self.persistence.download.complete(transport,checked,report_status)
   except Exception:return self._finalize(checked,"failed",False,0,0,False,"unknown_error","Historical Ads report processing failed safely.")
   received=getattr(result,"rows_validated",0);saved=getattr(result,"rows_persisted",0)
   if result.status in ("success","valid_empty"):
    message="Historical Ads sync completed." if persist else "Historical Ads report download validation completed without persistence."
    return self._finalize(checked,"succeeded" if persist else "validation_succeeded",True,received,saved,result.status=="valid_empty",None,message)
   return self._finalize(checked,"failed",False,received,0,False,result.status,"Historical Ads report processing failed safely.")
  error="report_failed" if report_status.status in ("failed","cancelled") else "validation_error"
  return self._finalize(checked,"failed",False,0,0,False,error,"Historical Ads report reached a terminal failure state.")
 def _release(self,run,claim):
  try:self.repository.save_report_check(replace(run,report_last_checked_at=self.now()),claim)
  except Exception:pass
 def _finalize(self,starting,status,success,received,saved,empty,error,message):
  completed=self.now();run=replace(starting,finished_at=completed,success=success,status="completed" if success else "failed",report_rows_received=received,rows_normalized=received if success else 0,rows_saved=saved,error_code=error,safe_error_message=None if success else message,report_last_checked_at=starting.report_last_checked_at or completed)
  try:self.repository.save_sync_run(run)
  except Exception:return self._result("failed",starting,"Historical Ads sync finalization failed.","run_finalization_error",completed)
  return self._result(status,run,message,error,completed,empty)
 def _result(self,status,run,message,error=None,completed=None,empty=False):
  return AdsManualHistoricalSyncResult(status,run.sync_id if run else None,run.started_at if run else None,completed,run.rows_saved if run and completed else 0,empty,message,error,run.amazon_report_status if run else None,run.report_created_at if run else None,run.report_last_checked_at if run else None)
 @staticmethod
 def _api_status(error):return "auth_error" if error.status_code in (401,403) else "rate_limited" if error.status_code==429 else "remote_error"
