import re
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from app.amazon_ads.live_models import AdsLiveEntityValidationResult
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin,login

NOW=datetime(2026,2,1,tzinfo=timezone.utc)
class Service:
 def __init__(self,status="success"):self.status=status;self.confirmations=[]
 def run(self,confirm):self.confirmations.append(confirm);return AdsLiveEntityValidationResult(self.status,NOW,NOW,"ready",{"configured":True,"discovered":1,"matched":True},{"records_received":1,"records_valid":1,"records_invalid":0,"duplicate_count":0,"bounded":True},(),())
def csrf(client):return re.search(r'data-csrf="([^"]+)"',client.get("/dashboard").text).group(1)
def setup(monkeypatch,service):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");monkeypatch.setattr(ads,"_live_entity_validation_service",lambda:service);return TestClient(app)

def test_entity_validation_api_auth_csrf_and_body_isolation(monkeypatch):
 service=Service();client=setup(monkeypatch,service);assert client.post("/api/ads/live-entity-validation",json={"confirm_live_read":True}).status_code==401;login(client);assert client.post("/api/ads/live-entity-validation",json={"confirm_live_read":True}).status_code==403
 response=client.post("/api/ads/live-entity-validation",json={"confirm_live_read":True,"profile_id":"override","region":"NA","client_secret":"override"},headers={"X-CSRF-Token":csrf(client)})
 assert response.status_code==200 and response.json()["status"]=="success" and service.confirmations==[True] and "override" not in response.text

def test_confirmation_and_readiness_blocks_map_safely(monkeypatch):
 confirmation=Service("blocked_confirmation");client=setup(monkeypatch,confirmation);login(client);token=csrf(client);assert client.post("/api/ads/live-entity-validation",json={"confirm_live_read":False},headers={"X-CSRF-Token":token}).status_code==400
 blocked=Service("blocked_readiness");monkeypatch.setattr(ads,"_live_entity_validation_service",lambda:blocked);assert client.post("/api/ads/live-entity-validation",json={"confirm_live_read":True},headers={"X-CSRF-Token":token}).status_code==422
