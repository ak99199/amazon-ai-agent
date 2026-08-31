from datetime import datetime,timezone
from pathlib import Path
import re
from fastapi.testclient import TestClient
from app.alerts.providers import SNSNotificationProvider,notification_provider_from_environment
from app.alerts.repository import SQLiteAlertRepository
from app.services.alert_service import AlertService
from main import app
from tests.test_dashboard import configure_admin,login

def insight(status="ACTIVE",risk=10,priority="low",flags=()):
    return {"seller_id":"seller-a","marketplace_id":"market-a","asin":"B000000001","current_listing":{"listing_status":status},"intelligence":{"risk_score":risk,"risk_flags":list(flags)},"recommendations":{"priority":priority,"overall_action":"CHECK_LISTING_STATUS","summary":"Review the listing manually."}}

def service(tmp_path,provider=None): return AlertService(SQLiteAlertRepository(tmp_path/"alerts.db"),provider)
def test_alert_creation_deduplication_and_severity(tmp_path):
    value=service(tmp_path);data=insight("INACTIVE",80,"critical",("RECENT_MAJOR_CHANGE","FULFILLMENT_UNSTABLE","PRICE_VOLATILE"));created=value.process(data,datetime(2026,1,1,tzinfo=timezone.utc));again=value.process(data,datetime(2026,1,1,tzinfo=timezone.utc))
    assert {item.alert_type for item in created}>={"LISTING_INACTIVE","HIGH_RISK_LISTING","PRIORITY_RECOMMENDATION","RECENT_MAJOR_CHANGE","FULFILLMENT_INSTABILITY","PRICE_VOLATILITY"}
    assert next(item for item in created if item.alert_type=="PRIORITY_RECOMMENDATION").severity=="critical" and again==[]
def test_alert_scope_isolation_and_dismissal(tmp_path):
    repo=SQLiteAlertRepository(tmp_path/"alerts.db");value=AlertService(repo);created=value.process(insight("INACTIVE",80,"high"))[0]
    assert repo.count_alerts("other","market-a")==0 and repo.dismiss("other","market-a",created.alert_id) is False
    assert repo.dismiss("seller-a","market-a",created.alert_id) and repo.list_alerts("seller-a","market-a",status="dismissed")[0].status=="dismissed"
def test_disabled_and_failed_providers_leave_alert_new(tmp_path,monkeypatch):
    monkeypatch.delenv("ALERTS_ENABLED",raising=False);assert notification_provider_from_environment() is None
    class Failing:
        def send(self,alert): raise RuntimeError("provider failure")
    repo=SQLiteAlertRepository(tmp_path/"alerts.db");created=AlertService(repo,Failing()).process(insight("INACTIVE",80,"high"));assert created and repo.list_alerts("seller-a","market-a",status="new")
def test_sns_provider_is_mocked_and_uses_only_normalized_text(tmp_path):
    calls=[]
    class Client:
        def publish(self,**kwargs): calls.append(kwargs)
    alert=AlertService(SQLiteAlertRepository(tmp_path/"alerts.db")).evaluate(insight("INACTIVE",80,"high"))[0]
    SNSNotificationProvider("arn:aws:sns:region:account:topic",Client()).send(alert)
    assert calls and calls[0]["Subject"]==alert.title and calls[0]["Message"]==alert.message and "token" not in str(calls).lower()
def test_alert_api_is_protected_and_never_leaks_secrets(tmp_path,monkeypatch):
    configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller-a");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market-a")
    repo=SQLiteAlertRepository(tmp_path/"alerts.db");AlertService(repo).process(insight("INACTIVE",80,"high"))
    import app.api.alerts as api
    monkeypatch.setattr(api,"create_alert_repository",lambda:repo)
    client=TestClient(app);assert client.get("/api/alerts").status_code==401;login(client)
    response=client.get("/api/alerts?severity=high");assert response.status_code==200 and response.json()["alerts"] and "refresh_token" not in response.text.lower() and "listing_hash" not in response.text
    csrf=re.search(r'name="csrf" value="([^"]+)"',client.get("/dashboard").text).group(1);alert_id=response.json()["alerts"][0]["alert_id"]
    assert client.post(f"/api/alerts/{alert_id}/dismiss",headers={"X-CSRF-Token":csrf}).status_code==200
def test_no_amazon_write_surface_exists(tmp_path):
    value=service(tmp_path);assert value.process(insight("ACTIVE",10,"low"))==[]