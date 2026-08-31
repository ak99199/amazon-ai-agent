import re
from fastapi.testclient import TestClient
from app.api import ads
from app.amazon_ads.sync_models import AdsSyncGateResult
from main import app
from tests.test_dashboard import configure_admin,login
class Service:
 def status(self,*args):return {"gate":{"allowed":True,"mode":"mock","status_code":"allowed_mock","status_message":"allowed"},"latest_sync":None}
 def run(self,*args,**kwargs):
  class Result:
   def public_dict(self):return {"sync_id":"id","mode":"mock","success":True,"status":"completed"}
  return Result()
def test_sync_api_is_authenticated_csrf_protected_and_safe(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market")
 monkeypatch.setattr(ads,"_sync_service",lambda repository:Service())
 client=TestClient(app);assert client.get("/api/ads/sync/status").status_code==401;login(client)
 assert client.post("/api/ads/sync",json={"window_days":7}).status_code==403
 csrf=re.search(r'data-csrf="([^"]+)"',client.get("/dashboard").text).group(1);response=client.post("/api/ads/sync",json={"window_days":7},headers={"X-CSRF-Token":csrf})
 assert response.status_code==200 and response.json()["mode"]=="mock" and "client_secret" not in response.text
