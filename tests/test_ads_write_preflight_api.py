import re
from types import SimpleNamespace
from fastapi.testclient import TestClient
from main import app
from app.api import ads
from tests.test_dashboard import configure_admin,login
class Service:
 def __init__(self):self.calls=[]
 def preflight(self,*args):self.calls.append(args);return SimpleNamespace(status="exact_value_required",public_dict=lambda:{"status":"exact_value_required","eligible":False,"dry_run":True,"message":"No Amazon Ads change is sent."})
def token(client):return re.search(r'data-csrf="([^"]+)"',client.get("/dashboard").text).group(1)
def test_preflight_endpoint_requires_auth_and_csrf(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p");client=TestClient(app);path="/api/ads/execution-plans/plan/preflight";body={"confirm_controlled_write_preflight":True}
 assert client.post(path,json=body).status_code==401;login(client);assert client.post(path,json=body).status_code==403
def test_endpoint_uses_server_scope_ignores_overrides_and_makes_no_network_call(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p");monkeypatch.setenv("AMAZON_SELLER_ID","s");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","m");service=Service();monkeypatch.setattr(ads,"AdsWritePreflightService",lambda *args:service);client=TestClient(app);login(client)
 body={"confirm_controlled_write_preflight":True,"seller_id":"attacker","profile_id":"attacker","bid":"999","endpoint":"https://attacker"};response=client.post("/api/ads/execution-plans/plan/preflight",json=body,headers={"X-CSRF-Token":token(client)})
 assert response.status_code==200 and response.json()["status"]=="exact_value_required" and service.calls==[("s","m","p","plan",True)] and "attacker" not in response.text
