from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin, login


def dashboard_context():
    portfolio = {"total_listings":0,"active_listings":0,"inactive_listings":0,"high_risk_count":0,"medium_risk_count":0,"low_risk_count":0,"stable_count":0,"recently_changed_count":0,"insufficient_history_count":0,"average_risk_score":0,"average_opportunity_score":0,"average_stability_score":0,"listings":[]}
    services = (None, SimpleNamespace(get_portfolio=lambda *args, **kwargs: SimpleNamespace(public_dict=lambda: portfolio)), None)
    return SimpleNamespace(seller_id="seller", marketplace_id="market"), services


def test_dashboard_ads_recommendations_empty_and_failure_safe(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setattr(routes, "_context", dashboard_context)
    monkeypatch.setattr(routes, "_ads_recommendations", lambda context: {"recommendations": [], "count": 0, "high_count": 0, "unavailable": False})
    client = TestClient(app); login(client)
    response = client.get("/dashboard")
    assert response.status_code == 200 and "Amazon Ads Recommendations" in response.text and "No Ads recommendations yet." in response.text


def test_dashboard_ads_recommendations_render_without_sensitive_values(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setattr(routes, "_context", dashboard_context)
    monkeypatch.setattr(routes, "_ads_recommendations", lambda context: {"count": 1, "high_count": 1, "unavailable": False, "recommendations": [{"priority":"high", "title":"Review spend without sales", "scope_type":"search_term", "scope_label":"safe term", "summary":"Safe summary", "metrics_snapshot":{"spend":"100", "sales":"0", "acos":None}}]})
    client = TestClient(app); login(client)
    response = client.get("/dashboard")
    assert response.status_code == 200 and "Review spend without sales" in response.text
    assert "TEST_CLIENT_SECRET" not in response.text and "refresh_token" not in response.text
