from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin,login
def production(ready):return {"unavailable":False,"approval_status":"approved" if ready else "pending","credential_configuration_complete":ready,"profile_selected":ready,"live_read_enabled":ready,"mock_mode":not ready,"region":"FE","blocking_reasons":[] if ready else ["approval_not_granted"],"manual_smoke_test_allowed":ready}
def page(monkeypatch,ready):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");state={"approval_status":"approved" if ready else "pending","config_status":"complete","profile_status":"selected","data_status":"no_data","ingestion_run_count":0,"last_ingestion_at":None,"overall_status":"ready" if ready else "approval_pending","production_live_read":production(ready)};monkeypatch.setattr(routes,"_ads_readiness",lambda context:state);client=TestClient(app);login(client);return client.get("/dashboard")
def test_button_only_when_ready_and_safety_copy(monkeypatch):
 assert "Validate Historical Report Lifecycle" not in page(monkeypatch,False).text;ready=page(monkeypatch,True);assert "Validate Historical Report Lifecycle" in ready.text and "may create a read-only Amazon Ads reporting job" in ready.text
def test_dashboard_script_shows_safe_completed_and_timeout_fields_without_url():
 script=open("static/dashboard.js",encoding="utf-8").read();assert "result.poll_attempts" in script and "result.last_report_status" in script and "result.download_ready" in script and "signed" not in script.lower()
def test_readiness_failure_hides_lifecycle_button(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");monkeypatch.setattr(routes,"_ads_readiness",lambda context:{"unavailable":True});client=TestClient(app);login(client);assert "Validate Historical Report Lifecycle" not in client.get("/dashboard").text
