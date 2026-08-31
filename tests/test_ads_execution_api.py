import re
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.api import ads
from app.database.ads_repository import AdsPerformanceRepository
from main import app
from tests.test_dashboard import configure_admin, login


def test_dry_run_api_is_authenticated_csrf_protected_and_never_executes(monkeypatch,tmp_path):
    configure_admin(monkeypatch); monkeypatch.setenv("AMAZON_SELLER_ID","seller"); monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market"); monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","profile")
    repository=AdsPerformanceRepository(tmp_path/"ads.db")
    repository.save(AdsPerformanceDaily("seller","market","profile",date.today(),"SP","campaign","Campaign",keyword_id="keyword",keyword_text="Keyword",impressions=1000,clicks=30,spend=Decimal("600"),orders=0,units=0,sales=Decimal("0")))
    monkeypatch.setattr(ads,"_services",lambda:(repository,None,None))
    client=TestClient(app)
    assert client.get("/api/ads/execution-plans").status_code==401
    login(client); actions=client.get("/api/ads/actions").json(); recommendation_id=actions["actions"][0]["recommendation_id"]
    assert client.post(f"/api/ads/actions/{recommendation_id}/dry-run").status_code==403
    csrf=re.search(r'data-csrf="([^"]+)"',client.get("/dashboard").text).group(1)
    client.post(f"/api/ads/actions/{recommendation_id}/decision",json={"status":"approved"},headers={"X-CSRF-Token":csrf})
    response=client.post(f"/api/ads/actions/{recommendation_id}/dry-run",headers={"X-CSRF-Token":csrf})
    assert response.status_code==200 and response.json()["dry_run"] is True
    assert client.get("/api/ads/execution-plans").status_code==200
    assert client.post("/api/ads/execute",headers={"X-CSRF-Token":csrf}).status_code==404
    assert "access_token" not in response.text and "client_secret" not in response.text
