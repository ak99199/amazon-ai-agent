import re
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import ads
from main import app
from tests.test_dashboard import configure_admin, login


class Service:
    def __init__(self):
        self.calls = []

    def propose(self, *args):
        self.calls.append(args)
        return SimpleNamespace(proposal_status="current_value_unavailable",
            public_dict=lambda: {"proposal_status": "current_value_unavailable",
                                 "eligible": False, "current_value": None,
                                 "proposed_value": None})


def token(client):
    return re.search(r'data-csrf="([^"]+)"', client.get("/dashboard").text).group(1)


def test_value_proposal_requires_auth_and_csrf(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setenv("AMAZON_ADS_PROFILE_ID", "p")
    client = TestClient(app)
    path = "/api/ads/execution-plans/plan/value-proposal"
    body = {"confirm_exact_value_proposal": True}
    assert client.post(path, json=body).status_code == 401
    login(client)
    assert client.post(path, json=body).status_code == 403


def test_request_numeric_and_scope_overrides_are_ignored(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setenv("AMAZON_ADS_PROFILE_ID", "p")
    monkeypatch.setenv("AMAZON_SELLER_ID", "s")
    monkeypatch.setenv("AMAZON_MARKETPLACE_ID", "m")
    service = Service()
    monkeypatch.setattr(ads, "AdsExactValueProposalService", lambda *args: service)
    client = TestClient(app)
    login(client)
    response = client.post("/api/ads/execution-plans/plan/value-proposal",
        json={"confirm_exact_value_proposal": True, "current_value": "999",
              "proposed_value": "888", "percentage": "90",
              "seller_id": "attacker", "endpoint": "https://attacker"},
        headers={"X-CSRF-Token": token(client)})
    assert response.status_code == 200
    assert service.calls == [("s", "m", "p", "plan", True)]
    assert "attacker" not in response.text and "999" not in response.text
