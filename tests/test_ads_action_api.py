import re
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.api import ads
from app.database.ads_repository import AdsPerformanceRepository
from main import app
from tests.test_dashboard import configure_admin, login


def test_actions_api_auth_csrf_and_internal_decision(monkeypatch, tmp_path):
    configure_admin(monkeypatch)
    monkeypatch.setenv("AMAZON_SELLER_ID", "seller"); monkeypatch.setenv("AMAZON_MARKETPLACE_ID", "market"); monkeypatch.setenv("AMAZON_ADS_PROFILE_ID", "profile")
    repository = AdsPerformanceRepository(tmp_path / "ads.db")
    row = AdsPerformanceDaily("seller", "market", "profile", date.today(), "SP", "campaign", "Campaign", keyword_id="keyword", keyword_text="Keyword", impressions=1000, clicks=30, spend=Decimal("600"), orders=0, units=0, sales=Decimal("0"))
    repository.save(row)
    monkeypatch.setattr(ads, "_services", lambda: (repository, None, None))
    client = TestClient(app)
    assert client.get("/api/ads/actions").status_code == 401
    login(client)
    actions = client.get("/api/ads/actions").json()
    assert actions["count"] > 0 and client.post("/api/ads/actions/unknown/decision", json={"status":"approved"}).status_code == 403
    csrf = re.search(r'data-csrf="([^"]+)"', client.get("/dashboard").text).group(1)
    recommendation_id = actions["actions"][0]["recommendation_id"]
    response = client.post(f"/api/ads/actions/{recommendation_id}/decision", json={"status":"approved","review_note":"reviewed"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200 and response.json()["status"] == "approved"
    assert client.post(f"/api/ads/actions/{recommendation_id}/decision", json={"status":"pending"}, headers={"X-CSRF-Token": csrf}).status_code == 422
    assert "access_token" not in response.text and "client_secret" not in response.text
    assert client.get("/api/ads/actions?limit=0").status_code == 422

