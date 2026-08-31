from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin,login
def context():
 p={"total_listings":0,"active_listings":0,"inactive_listings":0,"high_risk_count":0,"medium_risk_count":0,"low_risk_count":0,"stable_count":0,"recently_changed_count":0,"insufficient_history_count":0,"average_risk_score":0,"average_opportunity_score":0,"average_stability_score":0,"listings":[]};return SimpleNamespace(seller_id="s",marketplace_id="m"),(None,SimpleNamespace(get_portfolio=lambda *a,**k:SimpleNamespace(public_dict=lambda:p)),None)
def test_sync_dashboard_renders_safe_blocked_state(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setattr(routes,"_context",context);monkeypatch.setattr(routes,"_ads_sync",lambda c:{"unavailable":False,"gate":{"allowed":False,"mode":None,"status_code":"blocked_approval","status_message":"Approval pending"},"latest_sync":None})
 client=TestClient(app);login(client);response=client.get("/dashboard")
 assert "Amazon Ads Sync" in response.text and "blocked_approval" in response.text and "does not change campaigns" in response.text
