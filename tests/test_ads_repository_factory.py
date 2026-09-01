import pytest
from app.database.ads_base import AdsStorageConfigurationError,create_ads_repository
from app.database.ads_repository import AdsPerformanceRepository
from app.database.ads_dynamodb_repository import DynamoDbAdsHistoricalRepository
from tests.ads_dynamodb_fakes import Resource

def test_missing_and_explicit_sqlite_are_local_repositories(monkeypatch):
 monkeypatch.delenv("AMAZON_ADS_STORAGE_BACKEND",raising=False);assert isinstance(create_ads_repository(),AdsPerformanceRepository)
 assert isinstance(create_ads_repository("sqlite"),AdsPerformanceRepository)

@pytest.mark.parametrize("backend",["dynamodb","unknown"])
def test_unavailable_backends_fail_closed_without_sqlite_fallback(backend,tmp_path,monkeypatch):
 monkeypatch.chdir(tmp_path);monkeypatch.delenv("AMAZON_ADS_DYNAMODB_PERFORMANCE_TABLE",raising=False);monkeypatch.delenv("AMAZON_ADS_DYNAMODB_SYNC_RUNS_TABLE",raising=False)
 with pytest.raises(AdsStorageConfigurationError) as error:create_ads_repository(backend)
 assert "secret" not in str(error.value).lower() and not (tmp_path/"data"/"amazon_ai_agent.db").exists()

def test_lambda_persistence_requirement_blocks_sqlite():
 with pytest.raises(AdsStorageConfigurationError,match="requires persistent Ads storage"):create_ads_repository("sqlite",require_persistent=True)

def test_configured_dynamodb_uses_dedicated_tables_and_passes_persistent_gate(monkeypatch):
 resource=Resource();monkeypatch.setenv("AMAZON_ADS_DYNAMODB_PERFORMANCE_TABLE","performance");monkeypatch.setenv("AMAZON_ADS_DYNAMODB_SYNC_RUNS_TABLE","runs")
 result=create_ads_repository("dynamodb",True,resource,resource.client)
 assert isinstance(result,DynamoDbAdsHistoricalRepository) and result.performance_table.name=="performance" and result.sync_runs_table.name=="runs"

@pytest.mark.parametrize("missing",["performance","runs"])
def test_dynamodb_requires_both_ads_tables(missing,monkeypatch):
 monkeypatch.setenv("AMAZON_ADS_DYNAMODB_PERFORMANCE_TABLE","performance");monkeypatch.setenv("AMAZON_ADS_DYNAMODB_SYNC_RUNS_TABLE","runs");monkeypatch.delenv("AMAZON_ADS_DYNAMODB_PERFORMANCE_TABLE" if missing=="performance" else "AMAZON_ADS_DYNAMODB_SYNC_RUNS_TABLE")
 with pytest.raises(AdsStorageConfigurationError,match="not configured"):create_ads_repository("dynamodb",dynamodb_resource=Resource())
