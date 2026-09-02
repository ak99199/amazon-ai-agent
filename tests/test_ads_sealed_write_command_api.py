import re
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin,login
class TargetService:
 def __init__(self,*args):pass
 def resolve(self,*args):return SimpleNamespace(status="eligible_target_resolution",eligible=True)
class CommandService:
 calls=[]
 def __init__(self,*args):pass
 def seal(self,*args):self.calls.append(args);return SimpleNamespace(public_dict=lambda:{"status":"sealed"})
 def list_commands(self,*args):self.calls.append(args);return []
def token(c):return re.search(r'data-csrf="([^"]+)"',c.get("/dashboard").text).group(1)
def test_sealed_command_auth_csrf_and_override_resistance(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p");monkeypatch.setenv("AMAZON_SELLER_ID","s");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","m");monkeypatch.setattr(ads,"AdsWriteTargetResolutionService",TargetService);monkeypatch.setattr(ads,"AdsSealedWriteCommandService",CommandService);CommandService.calls=[]
 client=TestClient(app);path="/api/ads/write-intents/i/sealed-command";body={"confirm_seal_write_command":True,"entity_id":"attacker","direction":"decrease","proposed_value":"999","endpoint":"https://attacker","method":"PATCH","payload":{"bid":999}}
 assert client.post(path,json=body).status_code==401;login(client);assert client.post(path,json=body).status_code==403
 response=client.post(path,json=body,headers={"X-CSRF-Token":token(client)});assert response.status_code==200 and CommandService.calls[0][:5]==("s","m","p","i",True) and "attacker" not in response.text
def test_sealed_command_list_is_authenticated(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p");monkeypatch.setenv("AMAZON_SELLER_ID","s");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","m");monkeypatch.setattr(ads,"AdsSealedWriteCommandService",CommandService);CommandService.calls=[];client=TestClient(app)
 assert client.get("/api/ads/sealed-write-commands").status_code==401;login(client);assert client.get("/api/ads/sealed-write-commands?status=sealed&limit=10").status_code==200 and CommandService.calls==[("s","m","p","sealed",10)]
