from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin,login
def context():
 p={"total_listings":0,"active_listings":0,"inactive_listings":0,"high_risk_count":0,"medium_risk_count":0,"low_risk_count":0,"stable_count":0,"recently_changed_count":0,"insufficient_history_count":0,"average_risk_score":0,"average_opportunity_score":0,"average_stability_score":0,"listings":[]};return SimpleNamespace(seller_id="s",marketplace_id="m"),(None,SimpleNamespace(get_portfolio=lambda *a,**k:SimpleNamespace(public_dict=lambda:p)),None)
def state(active=False,cooldown=False,status="healthy",unavailable=False):return {"overall_status":status,"latest_run_status":"completed","last_success_at":"2026-02-10T00:00:00+00:00","last_success_rows_persisted":2,"active_run":active,"cooldown_active":cooldown,"cooldown_remaining_seconds":30,"data_freshness_status":"fresh","last_report_date":"2026-02-09","recent_runs":[{"started_at":"safe-time","completed_at":"safe-time","status":"completed","rows_persisted":2,"error_code":None}],"unavailable":unavailable}
def page(monkeypatch,health,ready=True):
 configure_admin(monkeypatch);monkeypatch.setattr(routes,"_context",context);monkeypatch.setattr(routes,"_ads_historical_sync_health",lambda c:health);monkeypatch.setattr(routes,"_ads_readiness",lambda c:{"overall_status":"ready","production_live_read":{"approval_status":"approved","credential_configuration_complete":True,"profile_selected":True,"live_read_enabled":True,"mock_mode":False,"region":"FE","blocking_reasons":[],"manual_smoke_test_allowed":ready}});client=TestClient(app);login(client);return client.get("/dashboard")
def test_section_renders_health_freshness_history_and_safe_copy(monkeypatch):
 response=page(monkeypatch,state());assert response.status_code==200 and "Amazon Ads Historical Sync" in response.text and "Run Historical Ads Sync" in response.text and "Latest report date" in response.text and "does not modify campaigns" in response.text and "safe-time" in response.text
def test_active_cooldown_blocked_and_unavailable_states_disable_button(monkeypatch):
 for health,ready in ((state(active=True),True),(state(cooldown=True,status="cooldown"),True),(state(),False),(state(unavailable=True,status="unavailable"),True)):
  text=page(monkeypatch,health,ready).text;fragment=text.split("ads-historical-sync-button",1)[1].split(">",1)[0];assert "disabled" in fragment
def test_javascript_confirmation_csrf_body_busy_state_refresh_and_no_bypass():
 script=open("static/dashboard.js",encoding="utf-8").read();section=script.split('document.querySelectorAll(".ads-historical-sync-button")',1)[1]
 assert "window.confirm" in section and '"X-CSRF-Token":panel.dataset.csrf' in section and 'JSON.stringify({confirm_live_read:true})' in section and "button.disabled=true" in section and "Historical sync running..." in section and "/api/ads/historical-sync-health" in section and "/api/ads/historical-sync-runs?limit=10" in section and "force" not in section and "bypass" not in section
def test_health_failure_is_isolated_and_dashboard_still_renders(monkeypatch):
 response=page(monkeypatch,state(unavailable=True,status="unavailable"));assert response.status_code==200 and "Historical sync status unavailable" in response.text and "Seller Dashboard" in response.text
