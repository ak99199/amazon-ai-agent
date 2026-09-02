import re
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin,login

class Service:
 calls=[]
 def __init__(self,*args,**kwargs):pass
 def revalidate(self,*args):self.calls.append(args);return SimpleNamespace(reason_code="current",public_dict=lambda:{"status":"prepared","reason_code":"current"})
 def cancel(self,*args):self.calls.append(args);return SimpleNamespace(reason_code="cancelled",public_dict=lambda:{"status":"cancelled","reason_code":"cancelled"})
def token(c):return re.search(r'data-csrf="([^"]+)"',c.get("/dashboard").text).group(1)
def test_lifecycle_endpoints_require_auth_csrf_and_ignore_overrides(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p");monkeypatch.setenv("AMAZON_SELLER_ID","s");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","m");monkeypatch.setattr(ads,"AdsWriteIntentRevalidationService",Service);Service.calls=[]
 client=TestClient(app);path="/api/ads/write-intents/i/revalidate";body={"confirm_revalidation":True,"current_value":"999","seller_id":"other"}
 assert client.post(path,json=body).status_code==401;login(client);assert client.post(path,json=body).status_code==403
 response=client.post(path,json=body,headers={"X-CSRF-Token":token(client)});assert response.status_code==200 and Service.calls[-1]==("s","m","p","i",True)
 cancel=client.post("/api/ads/write-intents/i/cancel",json={"confirm_cancel_write_intent":True,"bid":"999"},headers={"X-CSRF-Token":token(client)});assert cancel.status_code==200 and Service.calls[-1]==("s","m","p","i",True)
