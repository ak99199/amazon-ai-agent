import re
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from app.amazon_ads.live_models import AdsLiveSmokeTestResult
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin,login

NOW=datetime(2026,2,1,tzinfo=timezone.utc)
class Service:
 def __init__(self):self.confirmations=[]
 def run(self,confirm):
  self.confirmations.append(confirm);return AdsLiveSmokeTestResult("success",NOW,NOW,"FE",True,"campaign_read",200,True,1,"Bounded read succeeded.")

def test_live_smoke_api_auth_csrf_confirmation_and_body_isolation(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");service=Service();monkeypatch.setattr(ads,"_live_smoke_test_service",lambda:service);client=TestClient(app)
 assert client.post("/api/ads/live-smoke-test",json={"confirm_live_read":True}).status_code==401;login(client)
 assert client.post("/api/ads/live-smoke-test",json={"confirm_live_read":True}).status_code==403
 csrf=re.search(r'data-csrf="([^"]+)"',client.get("/dashboard").text).group(1)
 response=client.post("/api/ads/live-smoke-test",json={"confirm_live_read":True,"client_secret":"injected","profile_id":"injected"},headers={"X-CSRF-Token":csrf})
 assert response.status_code==200 and response.json()["status"]=="success" and service.confirmations==[True] and "injected" not in response.text

def test_false_confirmation_maps_to_400(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market")
 class Blocked:
  def run(self,confirm):return AdsLiveSmokeTestResult("blocked_confirmation",NOW,NOW,"FE",True,"gate",None,False,0,"Explicit live-read confirmation is required.")
 monkeypatch.setattr(ads,"_live_smoke_test_service",lambda:Blocked());client=TestClient(app);login(client);csrf=re.search(r'data-csrf="([^"]+)"',client.get("/dashboard").text).group(1)
 assert client.post("/api/ads/live-smoke-test",json={"confirm_live_read":False},headers={"X-CSRF-Token":csrf}).status_code==400
