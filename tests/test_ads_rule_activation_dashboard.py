from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin,login

DEFAULT={"active":False,"using_default_thresholds":True,"rule_version_id":None,"thresholds":{"target_acos_percent":"30"},"rollback_available":False}
ACTIVE={"active":True,"using_default_thresholds":False,"rule_version_id":"A","version_name":"Version A","source":"manual","activated_at":"2026-01-01T00:00:00+00:00","thresholds":{"target_acos_percent":"30"},"rollback_available":True}

def page(monkeypatch,state):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","profile");monkeypatch.setattr(routes,"_ads_rule_versions",lambda context:state);client=TestClient(app);login(client);return client.get("/dashboard")

def test_default_rule_version_panel_and_safety_copy(monkeypatch):
 response=page(monkeypatch,{"active":DEFAULT,"versions":[],"unavailable":False})
 assert response.status_code==200 and "Amazon Ads Rule Versions" in response.text and "Using default/environment recommendation thresholds" in response.text
 assert "does not modify Amazon Ads campaigns, bids, budgets, keywords, or targeting" in response.text and "Rollback restores a previous internal recommendation rule version using activation history" in response.text

def test_persisted_proposed_diff_controls_and_approval_distinction(monkeypatch):
 candidate={"rule_version_id":"B","version_name":"Version B","status":"proposed","source_proposal_id":"proposal-B","created_at":"2026-01-02","diff":[{"parameter_name":"target_acos_percent","current_value":"30","candidate_value":"25"}],"activation_eligible":True}
 response=page(monkeypatch,{"active":ACTIVE,"versions":[candidate],"unavailable":False})
 assert response.status_code==200 and "Version A" in response.text and "30 → 25" in response.text and "Activate Rule Version" in response.text and "Rollback to Previous Version" in response.text
 assert "proposal-B" in response.text and "Approved proposals do not change active recommendation rules automatically" in response.text

def test_ineligible_version_and_no_history_hide_controls(monkeypatch):
 active=dict(ACTIVE,rollback_available=False);candidate={"rule_version_id":"B","version_name":"Version B","status":"proposed","source_proposal_id":"proposal-B","created_at":"2026-01-02","diff":[],"activation_eligible":False};response=page(monkeypatch,{"active":active,"versions":[candidate],"unavailable":False})
 assert "Activate Rule Version" not in response.text and "Rollback to Previous Version" not in response.text

def test_rule_version_failure_is_isolated(monkeypatch):
 response=page(monkeypatch,{"active":None,"versions":[],"unavailable":True})
 assert response.status_code==200 and "Seller Dashboard" in response.text and "Rule version controls unavailable" in response.text
