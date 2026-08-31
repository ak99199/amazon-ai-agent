from fastapi.testclient import TestClient
from main import app
from tests.test_dashboard import configure_admin,login
def test_sync_health_dashboard_empty_is_safe(monkeypatch):
 configure_admin(monkeypatch);client=TestClient(app);login(client);response=client.get("/dashboard");assert response.status_code==200 and "Amazon Ads Sync Health" in response.text
