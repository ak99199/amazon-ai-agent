"""Persist only fully validated campaign DAILY report batches."""
from dataclasses import replace
from app.amazon_ads.live_models import AdsHistoricalReportPersistenceResult

class AdsLiveReportPersistenceService:
 def __init__(self,download_validation_service,repository,seller_id,marketplace_id):self.download=download_validation_service;self.repository=repository;self.seller_id=seller_id;self.marketplace_id=marketplace_id
 def run(self,confirm_live_read=False):
  result=self.download.run_with_validated(confirm_live_read,self.seller_id,self.marketplace_id,self._persist)
  if isinstance(result,AdsHistoricalReportPersistenceResult):return result
  return AdsHistoricalReportPersistenceResult(result.status,result.started_at,result.completed_at,result.report_kind,result.start_date,result.end_date,result.rows_validated,0,0,result.warnings,result.blocking_reasons,result.message)
 def _persist(self,rows,validation):
  if validation.status not in ("success","valid_empty") or validation.rows_truncated:return AdsHistoricalReportPersistenceResult("validation_error" if validation.rows_truncated else validation.status,validation.started_at,validation.completed_at,validation.report_kind,validation.start_date,validation.end_date,validation.rows_validated,0,0,validation.warnings,validation.blocking_reasons,"Report validation did not permit persistence.")
  settings=getattr(getattr(self.download.lifecycle,"readiness_service",None),"settings",None);profile_id=getattr(settings,"profile_id",None)
  rows=tuple(replace(row,seller_id=self.seller_id,marketplace_id=self.marketplace_id,profile_id=str(profile_id or row.profile_id)) for row in rows)
  try:
   if rows:self.repository.save_many(rows)
  except Exception:return AdsHistoricalReportPersistenceResult("persistence_error",validation.started_at,self.download.lifecycle.now(),validation.report_kind,validation.start_date,validation.end_date,validation.rows_validated,len(rows),0,validation.warnings,validation.blocking_reasons,"Historical report persistence failed.")
  return AdsHistoricalReportPersistenceResult(validation.status,validation.started_at,self.download.lifecycle.now(),validation.report_kind,validation.start_date,validation.end_date,validation.rows_validated,len(rows),len(rows),validation.warnings,validation.blocking_reasons,"Validated historical report rows were persisted idempotently." if rows else "Validated empty historical report required no persistence.")
