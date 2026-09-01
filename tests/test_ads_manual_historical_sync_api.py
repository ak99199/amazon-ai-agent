import re
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from app.amazon_ads.sync_models import AdsManualHistoricalSyncResult
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin,login
NOW=datetime(2026,2,10,tzinfo=timezone.utc)
class Service:
 def __init__(self,status="succeeded"):self.status=status;self.calls=[]
 def run(self,seller,market,confirm):self.calls.append((seller,market,confirm));return AdsManualHistoricalSyncResult(self.status,"run" if self.status=="succeeded" else None,NOW,NOW,2,False,"safe")
def setup(monkeypatch,service):configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");monkeypatch.setattr(ads,"_manual_historical_sync_service",lambda repository,context:service);return TestClient(app)
def csrf(client):return re.search(r'data-csrf="([^"]+)"',client.get("/dashboard").text).group(1)
def test_api_auth_csrf_and_body_scope_isolation(monkeypatch):
 service=Service();client=setup(monkeypatch,service);assert client.post("/api/ads/manual-historical-sync",json={"confirm_live_read":True}).status_code==401;login(client);assert client.post("/api/ads/manual-historical-sync",json={"confirm_live_read":True}).status_code==403
 response=client.post("/api/ads/manual-historical-sync",json={"confirm_live_read":True,"seller_id":"override","profile_id":"override","force":True},headers={"X-CSRF-Token":csrf(client)});assert response.status_code==200 and service.calls==[("seller","market",True)] and "override" not in response.text
def test_api_safe_status_mappings(monkeypatch):
 client=setup(monkeypatch,Service("blocked_confirmation"));login(client);token=csrf(client)
 for status,code in (("blocked_confirmation",400),("blocked_readiness",422),("already_running",409),("cooldown_active",429)):
  monkeypatch.setattr(ads,"_manual_historical_sync_service",lambda repository,context,s=status:Service(s));assert client.post("/api/ads/manual-historical-sync",json={"confirm_live_read":status!="blocked_confirmation"},headers={"X-CSRF-Token":token}).status_code==code
