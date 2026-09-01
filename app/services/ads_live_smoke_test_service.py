"""Explicit, bounded, read-only Amazon Ads live smoke test."""
from datetime import datetime,timezone
from app.amazon_ads.auth import AdsAuthenticationError
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.live_models import AdsLiveSmokeTestResult

class AdsLiveSmokeTestService:
 def __init__(self,readiness_service,adapter_factory,now=None,max_records=5):self.readiness_service=readiness_service;self.adapter_factory=adapter_factory;self.now=now or (lambda:datetime.now(timezone.utc));self.max_records=max(1,min(int(max_records),10))
 def run(self,confirm_live_read=False):
  started=self.now();readiness=self.readiness_service.get()
  if confirm_live_read is not True:return self._result("blocked_confirmation",started,readiness,"gate",None,False,0,"Explicit live-read confirmation is required.")
  if not readiness.manual_smoke_test_allowed:return self._blocked(started,readiness)
  try:
   adapter=self.adapter_factory();records=adapter.campaigns(self.readiness_service.settings.profile_id);count=min(len(records),self.max_records)
   return self._result("success",started,readiness,"campaign_read",200,True,count,"Bounded Amazon Ads campaign read succeeded.")
  except AdsAuthenticationError:return self._result("auth_error",started,readiness,"oauth",None,False,0,"Amazon Ads authentication failed.")
  except AdsApiClientError as error:
   status="auth_error" if error.status_code in (401,403) else "rate_limited" if error.status_code==429 else "remote_error"
   return self._result(status,started,readiness,"campaign_read",error.status_code,False,0,"Amazon Ads read could not be completed.")
  except Exception:return self._result("remote_error",started,readiness,"campaign_read",None,False,0,"Amazon Ads read could not be completed.")
 def _blocked(self,started,readiness):
  reason=readiness.blocking_reasons[0] if readiness.blocking_reasons else "live_read_disabled";status={"approval_not_granted":"blocked_approval","credential_configuration_incomplete":"blocked_config","profile_not_selected":"blocked_profile","region_invalid":"blocked_config","live_read_disabled":"blocked_live_disabled","mock_mode_enabled":"blocked_mock_mode"}.get(reason,"blocked_config")
  return self._result(status,started,readiness,"gate",None,False,0,"Live smoke test is blocked by production readiness.")
 def _result(self,status,started,readiness,stage,http_status,success,count,message):return AdsLiveSmokeTestResult(status,started,self.now(),readiness.region,readiness.profile_id_present,stage,http_status,success,count,message)
