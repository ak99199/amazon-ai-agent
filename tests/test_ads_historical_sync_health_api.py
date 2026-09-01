from fastapi.testclient import TestClient
from app.amazon_ads.sync_models import AdsHistoricalSyncHealth
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin,login
class Health:
 def __init__(self):self.calls=[]
 def get(self,s,m):self.calls.append((s,m));return AdsHistoricalSyncHealth("healthy","completed","safe","safe","safe",2,False,False,0,"fresh",1,"2026-02-09",1,0,(),())
def test_health_api_auth_scope_safe_output_and_no_network_factory(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");service=Health();monkeypatch.setattr(ads,"_historical_sync_health_service",lambda repository:service);client=TestClient(app);assert client.get("/api/ads/historical-sync-health").status_code==401;login(client);response=client.get("/api/ads/historical-sync-health");assert response.status_code==200 and service.calls==[("seller","market")] and not any(secret in response.text for secret in ("Authorization","refresh_token","signed","raw"))
