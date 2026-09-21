from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.web import routes
from main import app
from tests.test_dashboard import configure_admin,login

def test_dashboard_ads_readiness_is_safe(monkeypatch):
    configure_admin(monkeypatch)
    portfolio={"total_listings":0,"active_listings":0,"inactive_listings":0,"high_risk_count":0,"medium_risk_count":0,"low_risk_count":0,"stable_count":0,"recently_changed_count":0,"insufficient_history_count":0,"average_risk_score":0,"average_opportunity_score":0,"average_stability_score":0,"listings":[]}
    context=SimpleNamespace(seller_id="s",marketplace_id="m")
    services=(None,SimpleNamespace(get_portfolio=lambda *args,**kwargs:SimpleNamespace(public_dict=lambda:portfolio)),None)
    monkeypatch.setattr(routes,"_context",lambda:(context,services))
    monkeypatch.setattr(routes,"_ads_readiness",lambda context:{"approval_status":"pending","config_status":"incomplete","profile_status":"not_selected","data_status":"no_data","ingestion_run_count":0,"last_ingestion_at":None,"overall_status":"approval_pending"})
    client=TestClient(app);login(client);response=client.get("/dashboard")
    assert response.status_code==200 and "Amazon Ads Readiness" in response.text and "approval_pending" in response.text and "secret" not in response.text.lower()
    assert "Production live-read readiness unavailable." in response.text and "Run Live Read Smoke Test" not in response.text

def test_dashboard_ads_failure_isolated(monkeypatch):
    configure_admin(monkeypatch)
    monkeypatch.setattr(routes,"_ads_readiness",lambda context:{"overall_status":"error","unavailable":True})
    client=TestClient(app);login(client);response=client.get("/dashboard")
    assert response.status_code==200

@pytest.mark.parametrize("populated",[False,True])
def test_selected_profile_dashboard_uses_configured_dynamodb(monkeypatch,populated):
    import boto3
    from dataclasses import replace
    from datetime import date
    from app.database.ads_repository import AdsPerformanceRepository
    from tests.ads_dynamodb_fakes import Resource
    from tests.test_ads_dynamodb_performance_repository import row
    from tests.test_ads_control_plane_dynamodb_repository import repository as control_repository
    resource=Resource();control=control_repository();control.table.meta=SimpleNamespace(client=control.client);calls=[]
    def table(name):
        calls.append(name)
        return control.table if name=="control" else resource.Table(name)
    monkeypatch.setattr(boto3,"resource",lambda name:SimpleNamespace(Table=table))
    def forbidden(*args,**kwargs):raise AssertionError("SQLite must not be used")
    monkeypatch.setattr(AdsPerformanceRepository,"__init__",forbidden)
    monkeypatch.delenv("AMAZON_ADS_SECRET_ARN",raising=False)
    for key,value in {"AMAZON_ADS_STORAGE_BACKEND":"dynamodb","AMAZON_ADS_CONTROL_PLANE_BACKEND":"dynamodb","AMAZON_ADS_DYNAMODB_PERFORMANCE_TABLE":"performance","AMAZON_ADS_DYNAMODB_SYNC_RUNS_TABLE":"runs","AMAZON_ADS_DYNAMODB_CONTROL_PLANE_TABLE":"control","AMAZON_ADS_PROFILE_ID":"p","AMAZON_ADS_CLIENT_ID":"fake-id","AMAZON_ADS_CLIENT_SECRET":"fake-secret","AMAZON_ADS_REFRESH_TOKEN":"fake-refresh","AMAZON_ADS_APPROVAL_STATUS":"approved","AMAZON_ADS_REGION":"EU","AMAZON_ADS_LIVE_READ_ENABLED":"true","AMAZON_ADS_USE_MOCK_DATA":"false"}.items():monkeypatch.setenv(key,value)
    repository=routes._ads_repository()
    if populated:repository.historical.save_many([replace(row(),date=date.today())])
    context=SimpleNamespace(seller_id="s",marketplace_id="m")
    readiness=routes._ads_readiness(context);recommendations=routes._ads_recommendations(context);actions=routes._ads_actions(context)
    assert readiness["overall_status"]==("ready" if populated else "no_ads_data")
    assert readiness["performance_row_count"]==int(populated) and readiness["production_live_read"]["manual_smoke_test_allowed"]
    assert not recommendations["unavailable"] and not actions["unavailable"]
    assert bool(recommendations["count"])==populated and recommendations["count"]==actions["pending_count"]
    assert calls==["control","performance","runs"]*4
    assert not control.client.calls
    assert "fake-secret" not in str(readiness) and "fake-refresh" not in str(readiness)
    configure_admin(monkeypatch)
    portfolio=SimpleNamespace(get_portfolio=lambda *args,**kwargs:SimpleNamespace(public_dict=routes._empty))
    monkeypatch.setattr(routes,"_context",lambda:(context,(None,portfolio,None)))
    monkeypatch.setattr(routes,"_recent_alerts",lambda context:(0,[]))
    client=TestClient(app);login(client);response=client.get("/dashboard")
    assert response.status_code==200
    assert all(message not in response.text for message in ("Ads status unavailable.","Ads recommendations unavailable.","Ads Action Center unavailable.","fake-secret","fake-refresh"))

@pytest.mark.parametrize("helper",["_ads_readiness","_ads_recommendations","_ads_actions","_ads_execution_plans","_ads_sync","_ads_sync_health","_ads_historical_sync_health","_ads_scheduled_sync_health","_ads_intelligence","_ads_effectiveness","_ads_rule_tuning","_ads_rule_versions"])
def test_all_dashboard_ads_helpers_use_configured_storage_and_fail_safely(monkeypatch,helper):
    from app.api import ads
    calls=[];monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p")
    monkeypatch.setattr(ads,"create_ads_control_plane_repository",lambda:calls.append("control") or object())
    def unavailable():
        calls.append("historical")
        raise RuntimeError("sensitive-storage-sentinel")
    monkeypatch.setattr(ads,"create_ads_repository",unavailable)
    result=getattr(routes,helper)(SimpleNamespace(seller_id="s",marketplace_id="m"))
    assert calls==["control","historical"] and result["unavailable"]
    assert "sensitive-storage-sentinel" not in str(result)
