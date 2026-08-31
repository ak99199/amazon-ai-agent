import pytest
from app.config import ConfigurationError,Settings,require_dashboard_context

def test_dashboard_context_does_not_require_sp_api_credentials(monkeypatch):
    for name in ("AMAZON_SP_API_CLIENT_ID","AMAZON_SP_API_CLIENT_SECRET","AMAZON_SP_REFRESH_TOKEN"): monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv("AMAZON_SELLER_ID","seller"); monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market")
    context=require_dashboard_context()
    assert context.seller_id == "seller" and context.marketplace_id == "market"
    with pytest.raises(ConfigurationError): Settings.from_environment().require_complete()
def test_dashboard_context_requires_seller_and_marketplace(monkeypatch):
    monkeypatch.delenv("AMAZON_SELLER_ID",raising=False); monkeypatch.delenv("AMAZON_MARKETPLACE_ID",raising=False)
    with pytest.raises(ConfigurationError): require_dashboard_context()

def test_dashboard_route_works_without_sp_api_credentials(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from tests.test_dashboard import configure_admin, login
    configure_admin(monkeypatch)
    for name in ("AMAZON_SP_API_CLIENT_ID","AMAZON_SP_API_CLIENT_SECRET","AMAZON_SP_REFRESH_TOKEN"): monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv("AMAZON_SELLER_ID","seller"); monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market")
    client=TestClient(app); login(client)
    assert client.get("/dashboard").status_code == 200

def test_dashboard_route_fails_safely_without_scope(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from tests.test_dashboard import configure_admin, login
    configure_admin(monkeypatch); monkeypatch.delenv("AMAZON_SELLER_ID",raising=False); monkeypatch.delenv("AMAZON_MARKETPLACE_ID",raising=False)
    client=TestClient(app); login(client); response=client.get("/dashboard")
    assert response.status_code == 200 and "not configured" in response.text.lower() and "secret" not in response.text.lower()
