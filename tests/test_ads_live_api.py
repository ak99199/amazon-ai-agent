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
