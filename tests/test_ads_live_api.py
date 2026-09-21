from fastapi.testclient import TestClient
from app.api import ads
from app.amazon_ads.live_models import LiveReadStatus
from main import app
from tests.test_dashboard import configure_admin,login
class Service:
 def __init__(self):self.called=False
 def status(self,require_profile=True):return LiveReadStatus("disabled",False,True,"pending",False,False,False)
 def discover_profiles(self):self.called=True;return []
def test_live_read_api_is_protected_safe_and_does_not_read_when_disabled(monkeypatch):
 configure_admin(monkeypatch); service=Service();monkeypatch.setattr(ads,"_live_read_service",lambda **kwargs:service)
 client=TestClient(app);assert client.get("/api/ads/live-read/status").status_code==401;login(client)
 response=client.get("/api/ads/live-read/profiles")
 assert response.status_code==200 and response.json()["profiles"]==[] and service.called is False
 assert "client_secret" not in response.text and "access_token" not in response.text

def test_profiles_endpoint_discovers_without_selecting_profile(monkeypatch):
 import os,requests
 from types import SimpleNamespace
 from app.amazon_ads.models import AdsAccessToken
 configure_admin(monkeypatch)
 monkeypatch.delenv("AMAZON_ADS_SECRET_ARN",raising=False)
 monkeypatch.delenv("AMAZON_ADS_PROFILE_ID",raising=False)
 for key,value in {"AMAZON_ADS_CLIENT_ID":"fake-id","AMAZON_ADS_CLIENT_SECRET":"fake-secret","AMAZON_ADS_REFRESH_TOKEN":"fake-refresh","AMAZON_ADS_APPROVAL_STATUS":"approved","AMAZON_ADS_REGION":"FE","AMAZON_ADS_LIVE_READ_ENABLED":"true","AMAZON_ADS_USE_MOCK_DATA":"false"}.items():monkeypatch.setenv(key,value)
 monkeypatch.setattr(ads.AdsLwaAuthenticator,"get_access_token",lambda self:AdsAccessToken("fake-token","Bearer",3600))
 calls=[]
 def get(self,url,**kwargs):
  calls.append(url)
  assert "Amazon-Advertising-API-Scope" not in kwargs["headers"]
  return SimpleNamespace(ok=True,json=lambda:[{"profileId":1,"countryCode":"IN","raw":"not-returned"},{"profileId":2,"countryCode":"IN"},{"profileId":3,"countryCode":"JP"}])
 monkeypatch.setattr(requests.Session,"get",get)
 client=TestClient(app)
 assert client.get("/api/ads/live-read/profiles").status_code==401 and not calls
 login(client)
 result=client.get("/api/ads/live-read/profiles")
 assert result.status_code==200 and calls==["https://advertising-api-fe.amazon.com/v2/profiles"]
 payload=result.json()
 assert payload["india_profile_ids"]==["1","2"] and payload["profile_selection_required"]
 assert len(payload["profiles"])==3 and not payload["status"]["profile_selected"]
 assert os.getenv("AMAZON_ADS_PROFILE_ID") is None
 assert client.get("/api/ads/live-read/status").json()["mode"]=="blocked_profile"
 assert all(value not in result.text for value in ("fake-secret","fake-refresh","fake-token","not-returned"))

def test_profiles_endpoint_redacts_secret_loading_failure(monkeypatch):
 import boto3
 configure_admin(monkeypatch)
 monkeypatch.setenv("AMAZON_ADS_SECRET_ARN","configured-secret")
 def unavailable(name):raise RuntimeError("sensitive-sentinel")
 monkeypatch.setattr(boto3,"client",unavailable)
 client=TestClient(app);login(client)
 response=client.get("/api/ads/live-read/profiles")
 assert response.status_code==503 and "sensitive-sentinel" not in response.text
 status=client.get("/api/ads/live-read/status").json()
 assert status["ready"] is False and status["mode"]=="configuration_error"


def test_advertiser_accounts_probe_is_scoped_read_only_and_allowlisted(monkeypatch):
 import os,requests
 from types import SimpleNamespace
 from app.amazon_ads.models import AdsAccessToken
 configure_admin(monkeypatch)
 monkeypatch.delenv("AMAZON_ADS_SECRET_ARN",raising=False)
 for key,value in {"AMAZON_ADS_CLIENT_ID":"fake-id","AMAZON_ADS_CLIENT_SECRET":"fake-secret","AMAZON_ADS_REFRESH_TOKEN":"fake-refresh","AMAZON_ADS_PROFILE_ID":"1028270081837286","AMAZON_ADS_APPROVAL_STATUS":"approved","AMAZON_ADS_REGION":"EU","AMAZON_ADS_LIVE_READ_ENABLED":"true","AMAZON_ADS_USE_MOCK_DATA":"false"}.items():monkeypatch.setenv(key,value)
 monkeypatch.setattr(ads.AdsLwaAuthenticator,"get_access_token",lambda self:AdsAccessToken("fake-token","Bearer",3600))
 calls=[]
 def post(self,url,**kwargs):
  calls.append((url,kwargs))
  return SimpleNamespace(ok=True,json=lambda:{"advertiserAccounts":[{"advertiserAccountId":"a1","displayName":"EZZYHOME","isGlobalAccount":False,"alternateIds":[{"countryCode":"IN","entityId":"e1","profileId":"1028270081837286","private":"hidden"},{"countryCode":"IN","entityId":"e2","profileId":"other"}],"sellingAccounts":"not-returned"}],"accessToken":"not-returned"})
 monkeypatch.setattr(requests.Session,"post",post)
 client=TestClient(app)
 assert client.get("/api/ads/live-read/advertiser-accounts").status_code==401 and not calls
 login(client)
 result=client.get("/api/ads/live-read/advertiser-accounts")
 assert result.status_code==200 and result.json()=={"status":"ok","advertiserAccounts":[{"advertiserAccountId":"a1","displayName":"EZZYHOME","isGlobalAccount":False,"alternateIds":[{"countryCode":"IN","entityId":"e1","profileId":"1028270081837286","matchesConfiguredProfile":True},{"countryCode":"IN","entityId":"e2","profileId":"other","matchesConfiguredProfile":False}]}]}
 assert len(calls)==1 and calls[0][0]=="https://advertising-api-eu.amazon.com/adsApi/v1/query/advertiserAccounts"
 assert calls[0][1]["json"]=={} and calls[0][1]["headers"]=={"Amazon-Ads-ClientId":"fake-id","Authorization":"Bearer fake-token","Accept":"application/json","Content-Type":"application/json"}
 assert os.getenv("AMAZON_ADS_PROFILE_ID")=="1028270081837286"
 assert all(value not in result.text for value in ("fake-secret","fake-refresh","fake-token","not-returned","hidden"))


def test_advertiser_accounts_probe_requires_existing_readiness_gates(monkeypatch):
 import requests
 configure_admin(monkeypatch)
 monkeypatch.delenv("AMAZON_ADS_SECRET_ARN",raising=False)
 for key,value in {"AMAZON_ADS_CLIENT_ID":"fake-id","AMAZON_ADS_CLIENT_SECRET":"fake-secret","AMAZON_ADS_REFRESH_TOKEN":"fake-refresh","AMAZON_ADS_APPROVAL_STATUS":"approved","AMAZON_ADS_REGION":"EU","AMAZON_ADS_LIVE_READ_ENABLED":"true","AMAZON_ADS_USE_MOCK_DATA":"false"}.items():monkeypatch.setenv(key,value)
 monkeypatch.delenv("AMAZON_ADS_PROFILE_ID",raising=False)
 def forbidden(*args,**kwargs):raise AssertionError("Upstream request made while blocked")
 monkeypatch.setattr(requests.Session,"post",forbidden)
 client=TestClient(app);login(client)
 for key,value in (("AMAZON_ADS_APPROVAL_STATUS","pending"),("AMAZON_ADS_CLIENT_SECRET",""),("AMAZON_ADS_REGION","invalid"),("AMAZON_ADS_LIVE_READ_ENABLED","false"),("AMAZON_ADS_USE_MOCK_DATA","true")):
  original=__import__("os").getenv(key);monkeypatch.setenv(key,value)
  response=client.get("/api/ads/live-read/advertiser-accounts")
  assert response.status_code==200 and response.json()["status"]!="ok" and response.json()["advertiserAccounts"]==[]
  monkeypatch.setenv(key,original)


def test_advertiser_accounts_probe_classifies_and_sanitizes_errors(monkeypatch):
 import requests
 from types import SimpleNamespace
 from app.amazon_ads.models import AdsAccessToken
 configure_admin(monkeypatch)
 monkeypatch.delenv("AMAZON_ADS_SECRET_ARN",raising=False)
 for key,value in {"AMAZON_ADS_CLIENT_ID":"fake-id","AMAZON_ADS_CLIENT_SECRET":"fake-secret","AMAZON_ADS_REFRESH_TOKEN":"fake-refresh","AMAZON_ADS_APPROVAL_STATUS":"approved","AMAZON_ADS_REGION":"EU","AMAZON_ADS_LIVE_READ_ENABLED":"true","AMAZON_ADS_USE_MOCK_DATA":"false"}.items():monkeypatch.setenv(key,value)
 monkeypatch.setattr(ads.AdsLwaAuthenticator,"get_access_token",lambda self:AdsAccessToken("fake-token","Bearer",3600))
 client=TestClient(app);login(client)
 for code,expected in ((401,"auth_error"),(403,"unsupported_or_not_entitled"),(404,"unsupported_or_not_entitled"),(429,"rate_limited"),(500,"unavailable")):
  monkeypatch.setattr(requests.Session,"post",lambda self,url,**kwargs:SimpleNamespace(ok=False,status_code=code,json=lambda:{"secret":"not-returned"}))
  response=client.get("/api/ads/live-read/advertiser-accounts")
  assert response.status_code==200 and response.json()=={"status":expected,"advertiserAccounts":[]}
  assert "not-returned" not in response.text and "fake-token" not in response.text
 def unavailable(*args,**kwargs):raise requests.ConnectionError("sensitive-sentinel")
 monkeypatch.setattr(requests.Session,"post",unavailable)
 response=client.get("/api/ads/live-read/advertiser-accounts")
 assert response.json()=={"status":"unavailable","advertiserAccounts":[]} and "sensitive-sentinel" not in response.text
 monkeypatch.setattr(requests.Session,"post",lambda self,url,**kwargs:SimpleNamespace(ok=True,json=lambda:{"advertiserAccounts":{},"raw":"sensitive-sentinel"}))
 assert client.get("/api/ads/live-read/advertiser-accounts").json()=={"status":"unavailable","advertiserAccounts":[]}
