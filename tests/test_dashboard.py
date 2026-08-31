import re

import bcrypt
from fastapi.testclient import TestClient

from main import app


def configure_admin(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_ADMIN_USERNAME", "admin")
    monkeypatch.setenv(
        "DASHBOARD_ADMIN_PASSWORD_HASH",
        bcrypt.hashpw(b"password", bcrypt.gensalt()).decode(),
    )
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret")


def login(client: TestClient) -> None:
    login_page = client.get("/login")
    csrf = re.search(r'name="csrf" value="([^"]+)"', login_page.text).group(1)
    response = client.post(
        "/login",
        data={"username": "admin", "password": "password", "csrf": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_dashboard_loads_and_empty_state_is_safe(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.delenv("AMAZON_SP_API_CLIENT_ID", raising=False)
    client = TestClient(app)
    login(client)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Seller Dashboard" in response.text
    assert "No tracked listings" in response.text
    assert "secret" not in response.text.lower()
    assert "listing_hash" not in response.text


def test_detail_page_and_invalid_asin_are_safe(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.delenv("AMAZON_SP_API_CLIENT_ID", raising=False)
    client = TestClient(app)
    login(client)

    response = client.get("/dashboard/listings/not-a-valid-asin")

    assert response.status_code == 200
    assert "Listing not-a-valid-asin" in response.text
    assert "secret" not in response.text.lower()
    assert "listing_hash" not in response.text


def test_static_assets_load():
    assert TestClient(app).get("/static/styles.css").status_code == 200
