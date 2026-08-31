from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin, login


def context():
 portfolio={"total_listings":0,"active_listings":0,"inactive_listings":0,"high_risk_count":0,"medium_risk_count":0,"low_risk_count":0,"stable_count":0,"recently_changed_count":0,"insufficient_history_count":0,"average_risk_score":0,"average_opportunity_score":0,"average_stability_score":0,"listings":[]}
 return SimpleNamespace(seller_id="seller",marketplace_id="market"),(None,SimpleNamespace(get_portfolio=lambda *args,**kwargs:SimpleNamespace(public_dict=lambda:portfolio)),None)

def test_execution_dashboard_shows_simulation_only(monkeypatch):
 configure_admin(monkeypatch); monkeypatch.setattr(routes,"_context",context)
 monkeypatch.setattr(routes,"_ads_actions",lambda value:{"unavailable":False,"pending_count":0,"approved_count":1,"rejected_count":0,"dismissed_count":0,"actions":[{"recommendation_id":"id","priority":"high","status":"approved","recommendation_title":"Review","scope_type":"keyword","scope_label":"Keyword","summary":"Summary","suggested_action":"Review","review_note":None}]})
 monkeypatch.setattr(routes,"_ads_execution_plans",lambda value:{"unavailable":False,"plans":[{"eligible":True,"status":"eligible_dry_run","action_type":"BID_DIRECTION_REVIEW","direction":"decrease","created_at":"2026-01-01"}]})
 client=TestClient(app); login(client); response=client.get("/dashboard")
 assert "Generate Dry-Run Plan" in response.text and "Simulation only" in response.text and "eligible_dry_run" in response.text
 assert "updated on Amazon" not in response.text

def test_execution_dashboard_failure_isolated(monkeypatch):
 configure_admin(monkeypatch); monkeypatch.setattr(routes,"_context",context); monkeypatch.setattr(routes,"_ads_execution_plans",lambda value:{"unavailable":True,"plans":[]})
 client=TestClient(app); login(client)
 assert "Execution planning unavailable" in client.get("/dashboard").text
