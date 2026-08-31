from fastapi.testclient import TestClient
from main import app
from tests.test_dashboard import configure_admin,login
def test_sync_observability_history_routes_are_protected(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","s");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","m")
 client=TestClient(app);assert client.get("/api/ads/sync/observability").status_code==401;login(client)
 assert client.get("/api/ads/sync/observability").status_code==200 and client.get("/api/ads/sync/history?limit=1").status_code==200
