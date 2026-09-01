"""Manual, bounded validation of configured Ads profile and campaigns."""
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
from app.amazon_ads.auth import AdsAuthenticationError
from app.amazon_ads.campaigns import SponsoredProductsCampaignsService
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.live_models import AdsLiveEntityValidationResult

class AdsLiveEntityValidationService:
 def __init__(self,readiness_service,dependency_factory,now=None,max_campaigns=10):self.readiness_service=readiness_service;self.dependency_factory=dependency_factory;self.now=now or (lambda:datetime.now(timezone.utc));self.max_campaigns=max(1,min(int(max_campaigns),10))
 def run(self,confirm_live_read=False):
  started=self.now();ready=self.readiness_service.get();empty_profile={"configured":ready.profile_id_present,"discovered":0,"matched":False,"country_code":None,"currency_code":None,"account_type":None,"marketplace_id":None};empty_campaigns={"records_received":0,"records_valid":0,"records_invalid":0,"duplicate_count":0,"bounded":True}
  if confirm_live_read is not True:return self._result("blocked_confirmation",started,ready,empty_profile,empty_campaigns,(),ready.blocking_reasons)
  if not ready.manual_smoke_test_allowed:return self._result("blocked_readiness",started,ready,empty_profile,empty_campaigns,(),ready.blocking_reasons)
  try:profiles_service,adapter=self.dependency_factory()
  except Exception:return self._result("remote_error",started,ready,empty_profile,empty_campaigns,(),())
  try:profiles=profiles_service.list_profiles()
  except AdsAuthenticationError:return self._result("auth_error",started,ready,empty_profile,empty_campaigns,(),())
  except AdsApiClientError as error:return self._result(self._api_status(error),started,ready,empty_profile,empty_campaigns,(),())
  except Exception:return self._result("profile_discovery_error",started,ready,empty_profile,empty_campaigns,(),())
  configured=str(self.readiness_service.settings.profile_id);matches=[profile for profile in profiles if str(profile.profile_id)==configured];matched=matches[0] if matches else None
  profile={"configured":True,"discovered":len(profiles),"matched":bool(matched),"country_code":getattr(matched,"country_code",None),"currency_code":getattr(matched,"currency_code",None),"account_type":getattr(matched,"account_type",None),"marketplace_id":getattr(matched,"marketplace_string_id",None)}
  if not matched:return self._result("profile_not_found",started,ready,profile,empty_campaigns,(),())
  warnings=[]
  if ready.region=="FE" and profile["country_code"] not in (None,"IN"):warnings.append("Configured FE profile country is not India; review configuration manually.")
  try:rows=adapter.first_campaign_page(configured,self.max_campaigns)
  except AdsAuthenticationError:return self._result("auth_error",started,ready,profile,empty_campaigns,tuple(warnings),())
  except AdsApiClientError as error:return self._result(self._api_status(error),started,ready,profile,empty_campaigns,tuple(warnings),())
  except Exception:return self._result("remote_error",started,ready,profile,empty_campaigns,tuple(warnings),())
  if rows is None:return self._result("validation_error",started,ready,profile,empty_campaigns,tuple(warnings),())
  received=len(rows);valid=invalid=duplicates=0;seen=set()
  for row in rows:
   if not isinstance(row,dict):invalid+=1;continue
   try:
    item=SponsoredProductsCampaignsService._normalize(configured,row)
    if item.campaign_id in seen:duplicates+=1;continue
    self._validate_campaign(row,item);seen.add(item.campaign_id);valid+=1
   except (ValueError,TypeError,InvalidOperation):invalid+=1
  campaigns={"records_received":received,"records_valid":valid,"records_invalid":invalid,"duplicate_count":duplicates,"bounded":True}
  status="valid_empty" if received==0 else "validation_error" if valid==0 and (invalid or duplicates) else "success"
  return self._result(status,started,ready,profile,campaigns,tuple(warnings),())
 @staticmethod
 def _validate_campaign(row,item):
  if not item.campaign_id:raise ValueError("invalid campaign")
  if item.state is not None and str(item.state).lower() not in ("enabled","paused","archived"):raise ValueError("invalid state")
  if row.get("dailyBudget") is not None:
   amount=Decimal(str(row["dailyBudget"]));
   if not amount.is_finite() or amount<0:raise ValueError("invalid budget")
  for name in ("startDate","endDate"):
   if row.get(name) is not None:date.fromisoformat(str(row[name])[:10])
 @staticmethod
 def _api_status(error):return "auth_error" if error.status_code in (401,403) else "rate_limited" if error.status_code==429 else "remote_error"
 def _result(self,status,started,ready,profile,campaigns,warnings,blocking):return AdsLiveEntityValidationResult(status,started,self.now(),"ready" if ready.manual_smoke_test_allowed else "blocked",profile,campaigns,warnings,tuple(blocking))
