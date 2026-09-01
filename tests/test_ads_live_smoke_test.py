from datetime import datetime,timezone
import pytest
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.read_adapters import SponsoredProductsReadAdapter
from app.services.ads_live_smoke_test_service import AdsLiveSmokeTestService
from app.services.ads_production_readiness_service import AdsProductionReadinessService

NOW=datetime(2026,2,1,tzinfo=timezone.utc)
def readiness(approval="approved",settings=None,config=None):return AdsProductionReadinessService(settings or AdsSettings("id","secret","refresh","profile","FE"),config or AdsLiveReadConfig(True,False),approval)

@pytest.mark.parametrize("service",[readiness("pending"),readiness(settings=AdsSettings(None,"secret","refresh","profile","FE")),readiness(settings=AdsSettings("id","secret","refresh",None,"FE")),readiness(config=AdsLiveReadConfig(False,False)),readiness(config=AdsLiveReadConfig(True,True))])
def test_blocked_states_make_zero_network_factory_calls(service):
 calls=[];result=AdsLiveSmokeTestService(service,lambda:calls.append(True),now=lambda:NOW).run(True);assert result.status.startswith("blocked_") and calls==[] and not result.campaign_read_success

def test_confirmation_blocks_before_factory():
 calls=[];result=AdsLiveSmokeTestService(readiness(),lambda:calls.append(True),now=lambda:NOW).run(False);assert result.status=="blocked_confirmation" and calls==[]

def test_success_is_bounded_and_contains_no_sensitive_values():
 class Adapter:
  def campaigns(self,profile):assert profile=="profile";return list(range(100))
 result=AdsLiveSmokeTestService(readiness(),lambda:Adapter(),now=lambda:NOW,max_records=5).run(True);public=result.public_dict()
 assert result.status=="success" and result.records_observed==5 and result.campaign_read_success and result.request_stage=="campaign_read"
 assert not any(value in str(public) for value in ("secret","refresh","Authorization","access_token"))

def test_smoke_campaign_adapter_is_one_small_profile_scoped_page():
 class Client:
  def __init__(self):self.calls=[]
  def get_profile_scoped(self,path,params=None,profile_id=None):self.calls.append((path,params,profile_id));return {"campaigns":[]}
 client=Client();SponsoredProductsReadAdapter(client,max_pages=1,page_size=5).campaigns("profile")
 assert client.calls==[("/sp/campaigns",{"maxResults":5},"profile")]

@pytest.mark.parametrize("status,expected",[(401,"auth_error"),(403,"auth_error"),(429,"rate_limited"),(500,"remote_error")])
def test_http_errors_are_classified_safely(status,expected):
 class Adapter:
  def campaigns(self,profile):raise AdsApiClientError(status,"raw sensitive remote body",status in (429,500))
 result=AdsLiveSmokeTestService(readiness(),lambda:Adapter(),now=lambda:NOW).run(True);assert result.status==expected and result.http_status==status and "sensitive" not in result.message

def test_timeout_or_unknown_transport_error_is_safe_remote_error():
 class Adapter:
  def campaigns(self,profile):raise TimeoutError("credential-like raw details")
 result=AdsLiveSmokeTestService(readiness(),lambda:Adapter(),now=lambda:NOW).run(True);assert result.status=="remote_error" and "credential-like" not in result.message
