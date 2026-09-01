import re
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from app.amazon_ads.live_models import AdsLiveReportLifecycleValidationResult
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin,login
NOW=datetime(2026,2,10,tzinfo=timezone.utc)
class Service:
 def __init__(self,status="success"):self.status=status;self.confirmations=[]
 def run(self,confirm):self.confirmations.append(confirm);return AdsLiveReportLifecycleValidationResult(self.status,NOW,NOW,"ready","campaign","2026-02-08","2026-02-09",True,True,2,"completed",True,True,(),(),"safe")
def setup(monkeypatch,service):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");monkeypatch.setattr(ads,"_live_report_lifecycle_validation_service",lambda:service);return TestClient(app)
def csrf(client):return re.search(r'data-csrf="([^"]+)"',client.get("/dashboard").text).group(1)
def test_api_auth_csrf_confirmation_and_body_isolation(monkeypatch):
 service=Service();client=setup(monkeypatch,service);assert client.post("/api/ads/live-report-lifecycle-validation",json={"confirm_live_read":True}).status_code==401;login(client);assert client.post("/api/ads/live-report-lifecycle-validation",json={"confirm_live_read":True}).status_code==403
 response=client.post("/api/ads/live-report-lifecycle-validation",json={"confirm_live_read":True,"profile_id":"override","region":"NA","reportTypeId":"override","access_token":"override"},headers={"X-CSRF-Token":csrf(client)});assert response.status_code==200 and service.confirmations==[True] and "override" not in response.text
def test_api_maps_confirmation_and_readiness_blocks(monkeypatch):
 service=Service("blocked_confirmation");client=setup(monkeypatch,service);login(client);token=csrf(client);assert client.post("/api/ads/live-report-lifecycle-validation",json={"confirm_live_read":False},headers={"X-CSRF-Token":token}).status_code==400
 monkeypatch.setattr(ads,"_live_report_lifecycle_validation_service",lambda:Service("blocked_readiness"));assert client.post("/api/ads/live-report-lifecycle-validation",json={"confirm_live_read":True},headers={"X-CSRF-Token":token}).status_code==422
