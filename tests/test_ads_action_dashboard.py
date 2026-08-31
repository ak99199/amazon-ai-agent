from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin, login


def context():
    portfolio = {"total_listings":0,"active_listings":0,"inactive_listings":0,"high_risk_count":0,"medium_risk_count":0,"low_risk_count":0,"stable_count":0,"recently_changed_count":0,"insufficient_history_count":0,"average_risk_score":0,"average_opportunity_score":0,"average_stability_score":0,"listings":[]}
    return SimpleNamespace(seller_id="seller", marketplace_id="market"), (None, SimpleNamespace(get_portfolio=lambda *args, **kwargs: SimpleNamespace(public_dict=lambda: portfolio)), None)


def test_action_center_dashboard_states_and_safety_message(monkeypatch):
    configure_admin(monkeypatch); monkeypatch.setattr(routes, "_context", context)
    monkeypatch.setattr(routes, "_ads_actions", lambda value: {"unavailable":False,"pending_count":1,"approved_count":1,"rejected_count":1,"dismissed_count":1,"actions":[{"recommendation_id":"id","priority":"high","status":"approved","recommendation_title":"Review high ACOS","scope_type":"campaign","scope_label":"Campaign","summary":"Summary","suggested_action":"Human review only","review_note":None}]})
    client = TestClient(app); login(client); response = client.get("/dashboard")
    assert response.status_code == 200 and "Amazon Ads Action Center" in response.text and "Approved" in response.text
    assert "No Amazon Ads changes are executed" in response.text and "executed on Amazon" not in response.text


def test_action_center_failure_isolated(monkeypatch):
    configure_admin(monkeypatch); monkeypatch.setattr(routes, "_context", context); monkeypatch.setattr(routes, "_ads_actions", lambda value: {"unavailable":True,"actions":[],"count":0,"pending_count":0,"approved_count":0,"rejected_count":0,"dismissed_count":0})
    client = TestClient(app); login(client)
    assert "Ads Action Center unavailable" in client.get("/dashboard").text

