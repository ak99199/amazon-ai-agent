from fastapi.testclient import TestClient
from app.api import ads
from app.amazon_ads.live_models import LiveReadStatus
from main import app
from tests.test_dashboard import configure_admin,login
class Service:
 def __init__(self):self.called=False
 def status(self):return LiveReadStatus("disabled",False,True,"pending",False,False,False)
 def discover_profiles(self):self.called=True;return []
def test_live_read_api_is_protected_safe_and_does_not_read_when_disabled(monkeypatch):
 configure_admin(monkeypatch); service=Service();monkeypatch.setattr(ads,"_live_read_service",lambda:service)
 client=TestClient(app);assert client.get("/api/ads/live-read/status").status_code==401;login(client)
 response=client.get("/api/ads/live-read/profiles")
 assert response.status_code==200 and response.json()["profiles"]==[] and service.called is False
 assert "client_secret" not in response.text and "access_token" not in response.text
