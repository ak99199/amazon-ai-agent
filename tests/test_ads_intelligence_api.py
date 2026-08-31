from fastapi.testclient import TestClient

from app.api import ads
from app.amazon_ads.intelligence_models import AdsIntelligenceSummary
from main import app
from tests.test_dashboard import configure_admin, login


class IntelligenceService:
    allowed_windows = (7, 14, 30, 60, 90)
    def __init__(self, repository):
        pass
    def get(self, *args, **kwargs):
        from datetime import date
        return AdsIntelligenceSummary(30, date(2026, 1, 1), date(2026, 1, 30), {"totals": {}}, [], {}, [], [], [], [], [], [], {"total": 0}, {"pending": 0}, {"health_status": "never_synced"})


def test_intelligence_api_is_authenticated_and_read_only(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setenv("AMAZON_SELLER_ID", "seller")
    monkeypatch.setenv("AMAZON_MARKETPLACE_ID", "market")
    monkeypatch.setattr(ads, "AdsIntelligenceService", IntelligenceService)
    client = TestClient(app)
    assert client.get("/api/ads/intelligence").status_code == 401
    login(client)
    assert client.get("/api/ads/intelligence?window=30&limit=5").status_code == 200
    assert client.get("/api/ads/intelligence?window=8").status_code == 422
    assert client.post("/api/ads/intelligence").status_code in {403, 405}