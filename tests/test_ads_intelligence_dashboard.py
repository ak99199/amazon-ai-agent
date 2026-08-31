from fastapi.testclient import TestClient

from app.web import routes
from main import app
from tests.test_dashboard import configure_admin, login


def test_dashboard_renders_ads_intelligence_and_isolates_failure(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setattr(routes, "_ads_intelligence", lambda *args: {"window_days": 30, "summary": {"totals": {}}, "trend": [], "top_campaigns": [], "weak_campaigns": [], "top_keywords": [], "weak_keywords": [], "profitable_search_terms": [], "wasted_search_terms": [], "recommendations": {"total": 0, "by_code": {}}, "decisions": {"pending": 0, "approved": 0, "rejected": 0, "dismissed": 0}, "sync_health": {"health_status": "never_synced"}, "unavailable": False})
    client = TestClient(app); login(client)
    response = client.get("/dashboard")
    assert response.status_code == 200 and "Amazon Ads Intelligence" in response.text and "No historical Amazon Ads data available yet." in response.text