from types import SimpleNamespace
from fastapi.testclient import TestClient
from main import app
from app.api import ads
from tests.test_dashboard import configure_admin,login

def test_scheduled_health_requires_auth_and_returns_safe_server_scope(monkeypatch):
 configure_admin(monkeypatch);client=TestClient(app);assert client.get("/api/ads/scheduled-sync-health").status_code==401
 monkeypatch.setattr(ads,"_context",lambda:SimpleNamespace(seller_id="server-seller",marketplace_id="server-market"))
 class Service:
  def get(self,seller,market):
   assert (seller,market)==("server-seller","server-market")
   return SimpleNamespace(public_dict=lambda:{"enabled":False,"status":"disabled","warnings":[]})
 monkeypatch.setattr(ads,"_scheduled_sync_health_service",lambda repository:Service());login(client)
 response=client.get("/api/ads/scheduled-sync-health");assert response.status_code==200 and response.json()["status"]=="disabled" and "secret" not in response.text
