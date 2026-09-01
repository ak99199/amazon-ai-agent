from datetime import datetime,timezone
import pytest
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.models import AdsProfile
from app.services.ads_live_entity_validation_service import AdsLiveEntityValidationService
from app.services.ads_production_readiness_service import AdsProductionReadinessService

NOW=datetime(2026,2,1,tzinfo=timezone.utc)
def readiness(approval="approved",settings=None,config=None):return AdsProductionReadinessService(settings or AdsSettings("id","secret","refresh","configured-profile","FE"),config or AdsLiveReadConfig(True,False),approval)
class Profiles:
 def __init__(self,profiles=None,error=None):self.profiles=profiles or [];self.error=error
 def list_profiles(self):
  if self.error:raise self.error
  return self.profiles
class Adapter:
 def __init__(self,rows=None,error=None):self.rows=[] if rows is None else rows;self.error=error;self.calls=[]
 def first_campaign_page(self,profile,max_results):
  self.calls.append((profile,max_results))
  if self.error:raise self.error
  return self.rows
def dependencies(profiles=None,rows=None,profile_error=None,campaign_error=None):
 adapter=Adapter(rows,campaign_error);return lambda:(Profiles(profiles,profile_error),adapter),adapter
def matched(country="IN"):return AdsProfile("configured-profile",country,"INR",account_type="seller",marketplace_string_id="A21TJRUUN4KGV")

@pytest.mark.parametrize("ready",[readiness("pending"),readiness("rejected"),readiness(config=AdsLiveReadConfig(False,False)),readiness(config=AdsLiveReadConfig(True,True)),readiness(settings=AdsSettings(None,"secret","refresh","configured-profile","FE")),readiness(settings=AdsSettings("id","secret","refresh",None,"FE")),readiness(settings=AdsSettings("id","secret","refresh","configured-profile","XX"))])
def test_readiness_gates_make_zero_dependency_calls(ready):
 calls=[];result=AdsLiveEntityValidationService(ready,lambda:calls.append(True),now=lambda:NOW).run(True);assert result.status=="blocked_readiness" and calls==[]

def test_confirmation_false_makes_zero_dependency_calls():
 calls=[];assert AdsLiveEntityValidationService(readiness(),lambda:calls.append(True),now=lambda:NOW).run(False).status=="blocked_confirmation" and calls==[]

def test_configured_profile_matches_safe_metadata_and_bounded_campaign_read():
 factory,adapter=dependencies([matched(),AdsProfile("other","US","USD")],[{"campaignId":"1","name":"Campaign","state":"enabled","dailyBudget":"10.50","startDate":"2026-01-01"}]);result=AdsLiveEntityValidationService(readiness(),factory,now=lambda:NOW).run(True);public=result.public_dict()
 assert result.status=="success" and result.profile["matched"] and result.profile["discovered"]==2 and result.profile["country_code"]=="IN" and adapter.calls==[("configured-profile",10)]
 assert result.campaigns=={"records_received":1,"records_valid":1,"records_invalid":0,"duplicate_count":0,"bounded":True}
 assert not any(value in str(public) for value in ("secret","refresh","Authorization","access_token"))

def test_multiple_profiles_never_auto_select_when_configured_profile_missing():
 factory,adapter=dependencies([AdsProfile("first","IN"),AdsProfile("second","IN")],[]);result=AdsLiveEntityValidationService(readiness(),factory,now=lambda:NOW).run(True)
 assert result.status=="profile_not_found" and not result.profile["matched"] and adapter.calls==[]

def test_profile_discovery_failure_is_safe():
 factory,_=dependencies(profile_error=RuntimeError("raw sensitive profile response"));result=AdsLiveEntityValidationService(readiness(),factory,now=lambda:NOW).run(True);assert result.status=="profile_discovery_error" and "sensitive" not in str(result.public_dict())

def test_empty_campaign_account_is_valid():
 factory,_=dependencies([matched()],[]);result=AdsLiveEntityValidationService(readiness(),factory,now=lambda:NOW).run(True);assert result.status=="valid_empty" and result.campaigns["records_received"]==0

def test_malformed_duplicate_budget_state_and_date_rows_are_isolated():
 rows=[{"campaignId":"1","state":"enabled","dailyBudget":"10"},{"campaignId":"1","state":"enabled"},{"name":"missing id"},{"campaignId":"2","dailyBudget":"bad"},{"campaignId":"3","state":"invented"},{"campaignId":"4","startDate":"bad-date"}]
 factory,_=dependencies([matched()],rows);result=AdsLiveEntityValidationService(readiness(),factory,now=lambda:NOW).run(True)
 assert result.status=="success" and result.campaigns=={"records_received":6,"records_valid":1,"records_invalid":4,"duplicate_count":1,"bounded":True}

def test_fe_non_india_profile_returns_warning_without_autocorrection():
 factory,_=dependencies([matched("US")],[]);result=AdsLiveEntityValidationService(readiness(),factory,now=lambda:NOW).run(True);assert result.status=="valid_empty" and result.warnings

@pytest.mark.parametrize("status,expected",[(401,"auth_error"),(403,"auth_error"),(429,"rate_limited"),(500,"remote_error")])
def test_campaign_http_errors_are_safely_classified(status,expected):
 factory,_=dependencies([matched()],campaign_error=AdsApiClientError(status,"raw token body"));result=AdsLiveEntityValidationService(readiness(),factory,now=lambda:NOW).run(True);assert result.status==expected and "token" not in str(result.public_dict())

def test_campaign_timeout_is_remote_error():
 factory,_=dependencies([matched()],campaign_error=TimeoutError("raw timeout"));assert AdsLiveEntityValidationService(readiness(),factory,now=lambda:NOW).run(True).status=="remote_error"
