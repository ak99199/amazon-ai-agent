import re
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.amazon_ads.live_models import AdsLiveTargetingValidationResult
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin, login


NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)
COUNTS = {"records_received": 1, "records_valid": 1, "records_invalid": 0, "duplicate_count": 0, "bounded": True}


class Service:
    def __init__(self, status="success"):
        self.status = status
        self.confirmations = []

    def run(self, confirm):
        self.confirmations.append(confirm)
        return AdsLiveTargetingValidationResult(self.status, NOW, NOW, "ready", {"configured": True, "matched": True}, COUNTS, COUNTS, COUNTS, COUNTS, {"valid": 3, "invalid": 0, "unresolved": 0, "bounded": True}, (), ())


def setup(monkeypatch, service):
    configure_admin(monkeypatch)
    monkeypatch.setenv("AMAZON_SELLER_ID", "seller")
    monkeypatch.setenv("AMAZON_MARKETPLACE_ID", "market")
    monkeypatch.setattr(ads, "_live_targeting_validation_service", lambda: service)
    return TestClient(app)


def csrf(client):
    return re.search(r'data-csrf="([^"]+)"', client.get("/dashboard").text).group(1)


def test_api_requires_auth_csrf_and_ignores_scope_overrides(monkeypatch):
    service = Service()
    client = setup(monkeypatch, service)
    assert client.post("/api/ads/live-targeting-validation", json={"confirm_live_read": True}).status_code == 401
    login(client)
    assert client.post("/api/ads/live-targeting-validation", json={"confirm_live_read": True}).status_code == 403
    response = client.post("/api/ads/live-targeting-validation", json={"confirm_live_read": True, "profile_id": "override", "region": "NA", "client_secret": "override"}, headers={"X-CSRF-Token": csrf(client)})
    assert response.status_code == 200
    assert service.confirmations == [True]
    assert "override" not in response.text


def test_confirmation_and_readiness_blocks_map_safely(monkeypatch):
    service = Service("blocked_confirmation")
    client = setup(monkeypatch, service)
    login(client)
    token = csrf(client)
    assert client.post("/api/ads/live-targeting-validation", json={"confirm_live_read": False}, headers={"X-CSRF-Token": token}).status_code == 400
    monkeypatch.setattr(ads, "_live_targeting_validation_service", lambda: Service("blocked_readiness"))
    assert client.post("/api/ads/live-targeting-validation", json={"confirm_live_read": True}, headers={"X-CSRF-Token": token}).status_code == 422
