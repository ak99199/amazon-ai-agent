import pytest
from app.database.ads_repository import AdsPerformanceRepository
from app.database.ads_control_plane_factory import create_ads_control_plane_repository,AdsControlPlaneConfigurationError
from app.database.ads_control_plane_dynamodb_repository import DynamoDbAdsControlPlaneRepository
from fastapi.testclient import TestClient
from app.api import ads
from main import app
from tests.test_dashboard import configure_admin,login

class Resource:
 def __init__(self):self.names=[]
 def Table(self,name):self.names.append(name);return type("Table",(),{"name":name})()
class Client:pass

def test_default_and_explicit_sqlite(monkeypatch,tmp_path):
 monkeypatch.delenv("AMAZON_ADS_CONTROL_PLANE_BACKEND",raising=False)
 assert isinstance(create_ads_control_plane_repository(tmp_path/"local.db"),AdsPerformanceRepository)
 monkeypatch.setenv("AMAZON_ADS_CONTROL_PLANE_BACKEND","sqlite")
 assert isinstance(create_ads_control_plane_repository(tmp_path/"explicit.db"),AdsPerformanceRepository)
def test_unknown_and_missing_dynamodb_configuration_fail_without_fallback(monkeypatch,tmp_path):
 monkeypatch.setenv("AMAZON_ADS_CONTROL_PLANE_BACKEND","unknown")
 with pytest.raises(AdsControlPlaneConfigurationError):create_ads_control_plane_repository(tmp_path/"must-not-exist.db")
 assert not (tmp_path/"must-not-exist.db").exists()
 monkeypatch.setenv("AMAZON_ADS_CONTROL_PLANE_BACKEND","dynamodb");monkeypatch.delenv("AMAZON_ADS_DYNAMODB_CONTROL_PLANE_TABLE",raising=False)
 with pytest.raises(AdsControlPlaneConfigurationError):create_ads_control_plane_repository(tmp_path/"also-must-not-exist.db")
 assert not (tmp_path/"also-must-not-exist.db").exists()
def test_dynamodb_factory_uses_injected_dedicated_table(monkeypatch):
 monkeypatch.setenv("AMAZON_ADS_CONTROL_PLANE_BACKEND","dynamodb");monkeypatch.setenv("AMAZON_ADS_DYNAMODB_CONTROL_PLANE_TABLE","control-plane")
 resource=Resource();repo=create_ads_control_plane_repository(dynamodb_resource=resource,dynamodb_client=Client())
 assert isinstance(repo,DynamoDbAdsControlPlaneRepository) and resource.names==["control-plane"]
def test_ads_api_factory_failure_is_safe_503(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p")
 def unavailable():raise AdsControlPlaneConfigurationError("internal table detail")
 monkeypatch.setattr(ads,"create_ads_control_plane_repository",unavailable)
 client=TestClient(app);login(client);response=client.get("/api/ads/write-intents")
 assert response.status_code==503 and "internal table detail" not in response.text

def test_api_resolves_both_factories_and_reuses_local_sqlite(monkeypatch,tmp_path):
 control=AdsPerformanceRepository(tmp_path/"control.db");historical=AdsPerformanceRepository(tmp_path/"historical.db");calls=[]
 monkeypatch.setattr(ads,"create_ads_control_plane_repository",lambda:(calls.append("control") or control))
 monkeypatch.setattr(ads,"create_ads_repository",lambda:(calls.append("historical") or historical))
 repository,_,_=ads._services()
 assert calls==["control","historical"] and repository.control_plane is control and repository.historical is control

def test_api_keeps_mixed_and_dedicated_backends_distinct(monkeypatch):
 control=object();historical=object();calls=[]
 monkeypatch.setattr(ads,"create_ads_control_plane_repository",lambda:(calls.append("control") or control))
 monkeypatch.setattr(ads,"create_ads_repository",lambda:(calls.append("historical") or historical))
 repository,_,_=ads._services()
 assert calls==["control","historical"] and repository.control_plane is control and repository.historical is historical

def test_invalid_historical_factory_never_falls_back_to_sqlite(monkeypatch):
 control=object();calls=[]
 monkeypatch.setattr(ads,"create_ads_control_plane_repository",lambda:(calls.append("control") or control))
 def unavailable():calls.append("historical");raise RuntimeError("historical unavailable")
 monkeypatch.setattr(ads,"create_ads_repository",unavailable)
 with pytest.raises(RuntimeError):ads._services()
 assert calls==["control","historical"]
