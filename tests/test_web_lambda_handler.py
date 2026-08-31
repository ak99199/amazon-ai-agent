from pathlib import Path
from fastapi.testclient import TestClient
from main import app

def test_web_lambda_handler_imports_and_assets_exist():
    from web_lambda_handler import handler
    assert handler is not None
    assert Path("templates/dashboard.html").exists()
    assert Path("static/styles.css").exists()
def test_web_lambda_preserves_public_health_and_protected_dashboard():
    client=TestClient(app)
    assert client.get("/health").status_code == 200
    response=client.get("/dashboard",follow_redirects=False)
    assert response.status_code in (303,503)
    assert "secret" not in response.text.lower()
