from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin, login


class Repository:
    def get_active_rule_version(self, *args, **kwargs):
        return None

    def list_window(self, *args, **kwargs):
        return [AdsPerformanceDaily("seller", "market", "profile", date(2026, 1, 1), "SP", "campaign", "Campaign", keyword_id="keyword", keyword_text="Keyword", impressions=1000, clicks=30, spend=Decimal("100"), orders=2, units=2, sales=Decimal("500"))]


def test_recommendations_api_is_authenticated_read_only(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setenv("AMAZON_SELLER_ID", "seller"); monkeypatch.setenv("AMAZON_MARKETPLACE_ID", "market"); monkeypatch.setenv("AMAZON_ADS_PROFILE_ID", "profile")
    monkeypatch.setattr(ads, "_services", lambda: (Repository(), None, None))
    client = TestClient(app)
    assert client.get("/api/ads/recommendations").status_code == 401
    login(client)
    response = client.get("/api/ads/recommendations?window=30&limit=1")
    assert response.status_code == 200 and response.json()["count"] == 1
    post_response = client.post("/api/ads/recommendations")
    # CSRF middleware may reject unsafe API methods before router method matching.
    assert post_response.status_code in {403, 405}
    assert not any(getattr(route, "path", None) == "/api/ads/recommendations" and "POST" in (getattr(route, "methods", set()) or set()) for route in app.routes)
    assert client.get("/api/ads/recommendations?window=8").status_code == 422



