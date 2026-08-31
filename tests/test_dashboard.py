from fastapi.testclient import TestClient
from main import app
def test_dashboard_loads_and_empty_state_is_safe(monkeypatch):
    monkeypatch.delenv("AMAZON_SP_API_CLIENT_ID",raising=False); response=TestClient(app).get("/dashboard"); assert response.status_code == 200 and "Seller Dashboard" in response.text and "No tracked listings" in response.text
def test_detail_page_and_invalid_asin_are_safe(monkeypatch):
    monkeypatch.delenv("AMAZON_SP_API_CLIENT_ID",raising=False); response=TestClient(app).get("/dashboard/listings/not-a-valid-asin"); assert response.status_code == 200 and "Listing not-a-valid-asin" in response.text and "secret" not in response.text.lower() and "listing_hash" not in response.text
def test_static_assets_load(): assert TestClient(app).get("/static/styles.css").status_code == 200
