"""Manual, bounded Amazon Ads report-job lifecycle validation without download."""
from datetime import datetime,timedelta,timezone
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.report_transport import AdsReportTransportError
from app.amazon_ads.live_models import AdsLiveReportLifecycleValidationResult

class AdsLiveReportLifecycleValidationService:
 def __init__(self,readiness_service,dependency_factory,now=None,max_polls=5,sleeper=None):
  self.readiness_service=readiness_service;self.dependency_factory=dependency_factory;self.now=now or (lambda:datetime.now(timezone.utc));self.max_polls=max(1,min(int(max_polls),5));self.sleeper=sleeper or (lambda _:None)
 def run(self,confirm_live_read=False):
  started=self.now();ready=self.readiness_service.get();end=started.date()-timedelta(days=1);start=end-timedelta(days=1)
  if confirm_live_read is not True:return self._result("blocked_confirmation",started,ready,start,end,False,False,0,"not_started",False,False,"Explicit live-read confirmation is required.")
  if not ready.manual_smoke_test_allowed:return self._result("blocked_readiness",started,ready,start,end,False,False,0,"not_started",False,False,"Historical report lifecycle validation is blocked.")
  try:transport,reporting=self.dependency_factory();request=reporting.build_request("campaign",start,end);definition=self._definition(request,started.date())
  except (TypeError,ValueError):return self._result("validation_error",started,ready,start,end,False,False,0,"not_started",False,False,"Historical report request validation failed.")
  except Exception:return self._result("remote_error",started,ready,start,end,False,False,0,"not_started",False,False,"Historical report validation is unavailable.")
  try:report_id=transport.create(str(self.readiness_service.settings.profile_id),definition)
  except AdsReportTransportError:return self._result("validation_error",started,ready,start,end,True,False,0,"not_started",False,False,"Amazon Ads did not return a valid report identifier.")
  except AdsApiClientError as error:return self._error(error,started,ready,start,end,True,0)
  except Exception:return self._result("remote_error",started,ready,start,end,True,False,0,"not_started",False,False,"Historical report creation failed.")
  if not report_id:return self._result("validation_error",started,ready,start,end,True,False,0,"not_started",False,False,"Amazon Ads did not return a valid report identifier.")
  last="pending"
  for attempt in range(1,self.max_polls+1):
   try:last=transport.status(str(self.readiness_service.settings.profile_id),report_id).status
   except AdsApiClientError as error:return self._error(error,started,ready,start,end,True,attempt,True)
   except Exception:return self._result("remote_error",started,ready,start,end,True,True,attempt,last,False,False,"Historical report status lookup failed.")
   if last=="completed":return self._result("success",started,ready,start,end,True,True,attempt,last,True,True,"Historical report lifecycle completed; content was not downloaded.")
   if last in ("failed","cancelled"):return self._result("report_failed",started,ready,start,end,True,True,attempt,last,True,False,"Historical report reached a terminal failure state.")
   if last=="unknown":return self._result("validation_error",started,ready,start,end,True,True,attempt,last,True,False,"Amazon Ads returned an unknown report status.")
   if attempt<self.max_polls:self.sleeper(0)
  return self._result("poll_timeout",started,ready,start,end,True,True,self.max_polls,last,False,False,"Historical report is still processing after bounded polling.")
 @staticmethod
 def _definition(request,today):
  if request.report_level!="campaign" or request.ad_product!="SP" or not request.columns or not request.group_by or request.start_date>request.end_date or request.end_date>=today or (request.end_date-request.start_date).days>1:raise ValueError("invalid report request")
  columns=list(dict.fromkeys(("date","campaignId",*request.columns)))
  return {"name":"Historical report lifecycle validation","startDate":request.start_date.isoformat(),"endDate":request.end_date.isoformat(),"configuration":{"adProduct":"SPONSORED_PRODUCTS","groupBy":["campaign"],"columns":columns,"reportTypeId":"spCampaigns","timeUnit":"DAILY","format":"GZIP_JSON"}}
 @staticmethod
 def _status(error):return "auth_error" if error.status_code in (401,403) else "rate_limited" if error.status_code==429 else "remote_error"
 def _error(self,error,started,ready,start,end,created,polls,identified=False):return self._result(self._status(error),started,ready,start,end,created,identified,polls,"not_started" if not polls else "pending",False,False,"Amazon Ads report lifecycle request failed.")
 def _result(self,status,started,ready,start,end,created,identified,polls,last,terminal,download,message):return AdsLiveReportLifecycleValidationResult(status,started,self.now(),"ready" if ready.manual_smoke_test_allowed else "blocked","campaign",start.isoformat(),end.isoformat(),created,identified,polls,last,terminal,download,tuple(ready.warnings),tuple(ready.blocking_reasons),message)
