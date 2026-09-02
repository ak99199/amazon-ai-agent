import re
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin,login
class Service:
 calls=[]
 def __init__(self,*args):pass
 def resolve(self,*args):self.calls.append(args);return SimpleNamespace(status="target_resolution_unavailable",public_dict=lambda:{"status":"target_resolution_unavailable","eligible":False})
def token(c):return re.search(r'data-csrf="([^"]+)"',c.get("/dashboard").text).group(1)
def test_target_resolution_auth_csrf_and_override_resistance(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p");monkeypatch.setenv("AMAZON_SELLER_ID","s");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","m");monkeypatch.setattr(ads,"AdsWriteTargetResolutionService",Service);Service.calls=[]
 client=TestClient(app);path="/api/ads/write-intents/i/target-resolution";body={"confirm_target_resolution":True,"keyword_id":"attacker","scope_type":"campaign","action_type":"OTHER","direction":"decrease","bid":"999","endpoint":"https://attacker","method":"PATCH"}
 assert client.post(path,json=body).status_code==401;login(client);assert client.post(path,json=body).status_code==403
 response=client.post(path,json=body,headers={"X-CSRF-Token":token(client)});assert response.status_code==200 and Service.calls==[("s","m","p","i",True)] and "attacker" not in response.text
