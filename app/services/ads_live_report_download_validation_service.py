"""Bounded GZIP_JSON report download and structural validation; no persistence."""
from datetime import date
from decimal import Decimal,InvalidOperation
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.report_transport import AdsReportDownloadError,AdsReportDecompressionError,AdsReportParseError
from app.amazon_ads.live_models import AdsLiveReportDownloadValidationResult

class AdsLiveReportDownloadValidationService:
 def __init__(self,lifecycle_service,reporting_service,row_limit=100,compressed_limit=1048576,decompressed_limit=5242880):
  self.lifecycle=lifecycle_service;self.reporting=reporting_service;self.row_limit=max(1,min(int(row_limit),100));self.compressed_limit=max(1,int(compressed_limit));self.decompressed_limit=max(1,int(decompressed_limit))
 def run(self,confirm_live_read=False):
  return self.run_with_validated(confirm_live_read)
 def run_with_validated(self,confirm_live_read=False,seller_id="validation",marketplace_id="validation",on_validated=None):
  completed=lambda *args:self._completed(*args,seller_id,marketplace_id,on_validated)
  result=self.lifecycle.run_with_completed(confirm_live_read,completed)
  return result if isinstance(result,AdsLiveReportDownloadValidationResult) else self._from_lifecycle(result)
 def _completed(self,transport,profile_id,report_id,report_status,started,ready,start,end,polls,seller_id,marketplace_id,on_validated):
  try:rows,compressed_size,_=transport.download_gzip_json(report_status.location,self.compressed_limit,self.decompressed_limit)
  except AdsApiClientError as error:return self._result(self._api_status(error),started,ready,start,end,polls,True,False,False,False,0,0,0,0,False,"Historical report download failed.")
  except AdsReportDownloadError:return self._result("download_error",started,ready,start,end,polls,True,False,False,False,0,0,0,0,False,"Historical report download failed.")
  except AdsReportDecompressionError:return self._result("decompression_error",started,ready,start,end,polls,True,True,False,False,0,0,0,0,False,"Historical report decompression failed.")
  except AdsReportParseError:return self._result("parse_error",started,ready,start,end,polls,True,True,True,False,0,0,0,0,False,"Historical report parsing failed.")
  except TimeoutError:return self._result("remote_error",started,ready,start,end,polls,True,False,False,False,0,0,0,0,False,"Historical report download failed.")
  except Exception:return self._result("download_error",started,ready,start,end,polls,True,False,False,False,0,0,0,0,False,"Historical report download failed.")
  observed=len(rows);bounded=rows[:self.row_limit];valid=invalid=0;seen=set();normalized=[]
  for row in bounded:
   try:
    grain=self._validate_row(row,start,end)
    if grain in seen:raise ValueError("duplicate report grain")
    seen.add(grain);normalized.append(self.reporting.normalize_row(seller_id,marketplace_id,profile_id,row));valid+=1
   except Exception:invalid+=1
  status="valid_empty" if observed==0 else "partial_valid" if invalid else "success"
  result=self._result(status,started,ready,start,end,polls,True,True,True,True,observed,len(bounded),valid,invalid,observed>self.row_limit,"Historical report rows were validated without persistence.")
  return on_validated(tuple(normalized),result) if on_validated and status in ("success","valid_empty") else result
 @staticmethod
 def _validate_row(row,start,end):
  if not isinstance(row,dict) or not row.get("campaignId") or "date" not in row:raise ValueError("invalid campaign row")
  value=date.fromisoformat(str(row["date"])[:10])
  if value<start or value>end:raise ValueError("report date outside requested window")
  for field in ("impressions","clicks","purchases14d","unitsSold14d"):
   number=AdsLiveReportDownloadValidationService._number(row,field)
   if number!=number.to_integral_value():raise ValueError("invalid count")
  for field in ("cost","sales14d"):AdsLiveReportDownloadValidationService._number(row,field)
  return value.isoformat(),str(row["campaignId"])
 @staticmethod
 def _number(row,field):
  if field not in row:raise ValueError("missing requested metric")
  try:number=Decimal(str(row[field]))
  except (InvalidOperation,ValueError,TypeError):raise ValueError("invalid metric") from None
  if not number.is_finite() or number<0:raise ValueError("invalid metric")
  return number
 @staticmethod
 def _api_status(error):return "auth_error" if error.status_code in (401,403) else "rate_limited" if error.status_code==429 else "remote_error"
 def _from_lifecycle(self,value):
  return AdsLiveReportDownloadValidationResult(value.status,value.started_at,value.completed_at,value.readiness_status,value.report_kind,value.start_date,value.end_date,value.creation_attempted,value.poll_attempts,value.last_report_status,False,False,False,False,False,0,0,0,0,False,value.warnings,value.blocking_reasons,value.message)
 def _result(self,status,started,ready,start,end,polls,attempted,downloaded,decompressed,parsed,observed,validated,valid,invalid,truncated,message):
  return AdsLiveReportDownloadValidationResult(status,started,self.lifecycle.now(),"ready" if ready.manual_smoke_test_allowed else "blocked","campaign",start.isoformat(),end.isoformat(),True,polls,"completed",attempted,downloaded,downloaded,decompressed,parsed,observed,validated,valid,invalid,truncated,tuple(ready.warnings),tuple(ready.blocking_reasons),message)
