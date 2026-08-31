import re,bcrypt
from fastapi.testclient import TestClient
from main import app

def configure(monkeypatch):
    monkeypatch.setenv("DASHBOARD_ADMIN_USERNAME","admin")
    monkeypatch.setenv("DASHBOARD_ADMIN_PASSWORD_HASH",bcrypt.hashpw(b"password",bcrypt.gensalt()).decode())
    monkeypatch.setenv("SESSION_SECRET_KEY","test-session-secret")
def csrf(client):
    response=client.get("/login"); return re.search(r'name="csrf" value="([^"]+)"',response.text).group(1)
def login(client): return client.post("/login",data={"username":"admin","password":"password","csrf":csrf(client)},follow_redirects=False)
def test_dashboard_redirects_without_auth(monkeypatch):
    configure(monkeypatch); response=TestClient(app).get("/dashboard",follow_redirects=False); assert response.status_code == 303 and response.headers["location"] == "/login"
def test_login_failure_and_success(monkeypatch):
    configure(monkeypatch); client=TestClient(app); failed=client.post("/login",data={"username":"admin","password":"bad","csrf":csrf(client)}); assert failed.status_code == 401 and "Login failed" in failed.text
    assert login(client).status_code == 303 and client.get("/dashboard").status_code == 200
def test_logout_and_protected_api(monkeypatch):
    configure(monkeypatch); client=TestClient(app); assert client.get("/api/listings/x/history").status_code == 401; login(client); token=csrf(client); assert client.post("/logout",data={"csrf":token},follow_redirects=False).status_code == 303; assert client.get("/api/portfolio/insights").status_code == 401
def test_health_internal_and_headers(monkeypatch):
    configure(monkeypatch); client=TestClient(app); assert client.get("/health").status_code == 200; assert client.post("/api/internal/listings/snapshots/run").status_code == 404
    monkeypatch.setenv("ENABLE_INTERNAL_SNAPSHOT_ROUTE","true"); login(client); assert client.post("/api/internal/listings/snapshots/run").status_code == 403
    response=client.get("/dashboard"); assert response.headers["X-Frame-Options"] == "DENY" and "secret" not in response.text.lower()
def test_missing_auth_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("DASHBOARD_ADMIN_USERNAME",raising=False); assert TestClient(app).get("/api/listings/x/history").status_code == 503
