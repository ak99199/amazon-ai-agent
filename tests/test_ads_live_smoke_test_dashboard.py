from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin,login

def live(ready=False,approval="pending"):
 return {"approval_status":approval,"credential_configuration_complete":ready,"profile_selected":ready,"live_read_enabled":ready,"mock_mode":not ready,"region":"FE","manual_smoke_test_allowed":ready,"blocking_reasons":[] if ready else ["approval_not_granted"]}
def page(monkeypatch,state):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");monkeypatch.setattr(routes,"_ads_readiness",lambda context:state);client=TestClient(app);login(client);return client.get("/dashboard")
def base(value):return {"approval_status":value["approval_status"],"config_status":"complete","profile_status":"selected","data_status":"no_data","ingestion_run_count":0,"last_ingestion_at":None,"overall_status":"ready","production_live_read":value}

def test_pending_dashboard_blocks_button_and_shows_safety(monkeypatch):
 response=page(monkeypatch,base(live()));assert response.status_code==200 and "Production Live Read Readiness" in response.text and "approval is still pending" in response.text and "Run Live Read Smoke Test" not in response.text
 assert "does not modify campaigns, bids, budgets, keywords, or targeting" in response.text and "secret" not in response.text.lower()

def test_ready_dashboard_shows_explicit_manual_button(monkeypatch):
 response=page(monkeypatch,base(live(True,"approved")));assert response.status_code==200 and "Run Live Read Smoke Test" in response.text and "Region: FE" in response.text

def test_readiness_failure_is_isolated(monkeypatch):
 response=page(monkeypatch,{"unavailable":True});assert response.status_code==200 and "Seller Dashboard" in response.text and "Ads status unavailable" in response.text

def test_null_production_readiness_uses_backward_safe_fallback(monkeypatch):
 state=base(live());state["production_live_read"]=None;response=page(monkeypatch,state)
 assert response.status_code==200 and "Production live-read readiness unavailable." in response.text and "Run Live Read Smoke Test" not in response.text
