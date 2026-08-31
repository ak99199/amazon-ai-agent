from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.web import routes
from main import app
from tests.test_dashboard import configure_admin, login


def _listing(asin, priority="low", risk=10, title="Example product"):
    return {
        "asin": asin, "sku": f"SKU-{asin}", "title": title,
        "listing_status": "ACTIVE", "current_price": "100.00", "currency": "INR",
        "captured_at": "2026-08-31T00:00:00+00:00", "risk_score": risk,
        "opportunity_score": 55, "stability_score": 80, "data_confidence": "medium",
        "overall_action": "CHECK_LISTING_STATUS" if priority == "critical" else "KEEP_STABLE",
        "action_reason": "Listing status needs review." if priority == "critical" else "Listing is stable.", "priority": priority, "risk_flags": ["STATUS_UNSTABLE"] if priority == "critical" else [],
        "opportunity_flags": [], "days_tracked": 12, "snapshot_count": 3,
        "days_since_last_change": 1,
    }


def _install_dashboard_fakes(monkeypatch, listings):
    portfolio_data = {
        "total_listings": len(listings), "active_listings": len(listings), "inactive_listings": 0,
        "high_risk_count": sum(row["risk_score"] >= 70 for row in listings),
        "medium_risk_count": 0, "low_risk_count": 0,
        "stable_count": sum(row["overall_action"] == "KEEP_STABLE" for row in listings),
        "recently_changed_count": len(listings), "insufficient_history_count": 0,
        "average_risk_score": 42, "average_opportunity_score": 55,
        "average_stability_score": 80, "listings": listings,
    }
    portfolio = SimpleNamespace(
        get_portfolio=lambda *args, **kwargs: SimpleNamespace(public_dict=lambda: portfolio_data.copy())
    )
    result = {
        "current_listing": {"asin": "B0001", "sku": "SKU-B0001", "title": "Example product", "listing_status": "ACTIVE", "price": "100.00", "currency": "INR", "fulfillment_channel": "FBA"},
        "history_summary": {"snapshot_count": 1},
        "intelligence": {"risk_score": 90, "opportunity_score": 20, "stability_score": 30, "data_confidence": "medium", "days_tracked": 12, "days_since_last_change": 1, "risk_flags": ["STATUS_UNSTABLE"], "opportunity_flags": []},
        "recommendations": {"recommendations": [{"action": "CHECK_LISTING_STATUS", "priority": "critical", "reason": "Listing status needs review."}]},
        "explanation": {"headline": "Review listing status", "summary": "Review the provided listing status."},
    }
    insights = SimpleNamespace(get_insights=lambda *args, **kwargs: SimpleNamespace(public_dict=lambda: result.copy()))
    snapshot = SimpleNamespace(public_dict=lambda: {"captured_at": "2026-08-31T00:00:00+00:00", "price": "100.00", "currency": "INR", "listing_status": "ACTIVE", "changed": True})
    repo = SimpleNamespace(get_listing_history=lambda *args, **kwargs: [snapshot])
    context = SimpleNamespace(seller_id="seller", marketplace_id="marketplace")
    monkeypatch.setattr(routes, "_context", lambda: (context, (repo, portfolio, insights)))


def test_action_center_orders_actions_and_uses_friendly_labels(monkeypatch):
    configure_admin(monkeypatch)
    _install_dashboard_fakes(monkeypatch, [_listing("BLOW", "low", 5), _listing("BHIGH", "high", 80), _listing("BCRIT", "critical", 90)])
    monkeypatch.setattr(routes, "_recent_alerts", lambda context: (1, [{"severity":"high","asin":"BCRIT","title":"High-risk listing detected","created_at":"2026-01-01"}]))
    client = TestClient(app)
    login(client)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Today's Action Center" in response.text
    assert "Alerts" in response.text and "High-risk listing detected" in response.text
    assert "Check Listing Status" in response.text
    assert response.text.index("BCRIT") < response.text.index("BHIGH") < response.text.index("BLOW")
    assert ">2</strong>" in response.text  # critical and high need attention
    assert "listing_hash" not in response.text
    assert "refresh_token" not in response.text.lower()


def test_action_center_filters_are_deterministic():
    rows = [_listing("LOW", "low", 10), _listing("MEDIUM", "medium", 45), _listing("HIGH", "high", 85)]

    assert [row["asin"] for row in routes._apply_ui_filters(rows, "high", False)] == ["HIGH"]
    assert [row["asin"] for row in routes._apply_ui_filters(rows, None, True)] == ["HIGH"]
    assert routes.ACTION_LABELS["REVIEW_PRICE_VOLATILITY"] == "Review Price Changes"


def test_listing_detail_has_action_center_sections_and_handles_missing_values(monkeypatch):
    configure_admin(monkeypatch)
    _install_dashboard_fakes(monkeypatch, [_listing("B0001", "critical", 90, "")])
    monkeypatch.setattr(routes, "_recent_alerts", lambda context: (1, [{"severity":"high","asin":"BCRIT","title":"High-risk listing detected","created_at":"2026-01-01"}]))
    client = TestClient(app)
    login(client)

    response = client.get("/dashboard/listings/B0001")

    assert response.status_code == 200
    for heading in ("Current Listing", "Intelligence", "Recommended Actions", "AI Explanation", "Recent History"):
        assert heading in response.text
    assert "listing_hash" not in response.text
    assert "client_secret" not in response.text.lower()


def test_dashboard_remains_protected():
    response = TestClient(app).get("/dashboard", follow_redirects=False)
    assert response.status_code in (303, 401, 403, 503)