from fastapi.testclient import TestClient

from app.web import routes
from main import app
from tests.test_dashboard import configure_admin, login


def production(ready):
    return {"unavailable": False, "approval_status": "approved" if ready else "pending", "credential_configuration_complete": ready, "profile_selected": ready, "live_read_enabled": ready, "mock_mode": not ready, "region": "FE", "blocking_reasons": [] if ready else ["approval_not_granted"], "manual_smoke_test_allowed": ready}


def page(monkeypatch, ready):
    configure_admin(monkeypatch)
    monkeypatch.setenv("AMAZON_SELLER_ID", "seller")
    monkeypatch.setenv("AMAZON_MARKETPLACE_ID", "market")
    state = {"approval_status": "approved" if ready else "pending", "config_status": "complete", "profile_status": "selected", "data_status": "no_data", "ingestion_run_count": 0, "last_ingestion_at": None, "overall_status": "ready" if ready else "approval_pending", "production_live_read": production(ready)}
    monkeypatch.setattr(routes, "_ads_readiness", lambda context: state)
    client = TestClient(app)
    login(client)
    return client.get("/dashboard")


def test_button_only_when_ready_and_safety_copy(monkeypatch):
    assert "Validate Keywords &amp; Targets" not in page(monkeypatch, False).text
    ready = page(monkeypatch, True)
    assert "Validate Keywords &amp; Targets" in ready.text
    assert "does not modify bids, keywords, targets, campaigns, or budgets" in ready.text


def test_script_displays_safe_counts_and_bounded_unresolved_label():
    script = open("static/dashboard.js", encoding="utf-8").read()
    assert "result.keywords.records_received" in script
    assert "result.targets.records_received" in script
    assert "unresolved due to bounded validation" in script


def test_readiness_failure_hides_button(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setenv("AMAZON_SELLER_ID", "seller")
    monkeypatch.setenv("AMAZON_MARKETPLACE_ID", "market")
    monkeypatch.setattr(routes, "_ads_readiness", lambda context: {"unavailable": True})
    client = TestClient(app)
    login(client)
    assert "Validate Keywords &amp; Targets" not in client.get("/dashboard").text
