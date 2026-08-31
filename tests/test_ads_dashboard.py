from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin,login

def test_dashboard_ads_readiness_is_safe(monkeypatch):
    configure_admin(monkeypatch)
    portfolio={"total_listings":0,"active_listings":0,"inactive_listings":0,"high_risk_count":0,"medium_risk_count":0,"low_risk_count":0,"stable_count":0,"recently_changed_count":0,"insufficient_history_count":0,"average_risk_score":0,"average_opportunity_score":0,"average_stability_score":0,"listings":[]}
    context=SimpleNamespace(seller_id="s",marketplace_id="m")
    services=(None,SimpleNamespace(get_portfolio=lambda *args,**kwargs:SimpleNamespace(public_dict=lambda:portfolio)),None)
    monkeypatch.setattr(routes,"_context",lambda:(context,services))
    monkeypatch.setattr(routes,"_ads_readiness",lambda context:{"approval_status":"pending","config_status":"incomplete","profile_status":"not_selected","data_status":"no_data","ingestion_run_count":0,"last_ingestion_at":None,"overall_status":"approval_pending"})
    client=TestClient(app);login(client);response=client.get("/dashboard")
    assert response.status_code==200 and "Amazon Ads Readiness" in response.text and "approval_pending" in response.text and "secret" not in response.text.lower()

def test_dashboard_ads_failure_isolated(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setattr(routes,"_ads_readiness",lambda context:{"overall_status":"error","unavailable":True})
    client=TestClient(app);login(client);response=client.get("/dashboard")
    assert response.status_code==200