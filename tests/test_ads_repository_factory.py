import pytest
from app.database.ads_base import AdsStorageConfigurationError,create_ads_repository
from app.database.ads_repository import AdsPerformanceRepository

def test_missing_and_explicit_sqlite_are_local_repositories(monkeypatch):
 monkeypatch.delenv("AMAZON_ADS_STORAGE_BACKEND",raising=False);assert isinstance(create_ads_repository(),AdsPerformanceRepository)
 assert isinstance(create_ads_repository("sqlite"),AdsPerformanceRepository)

@pytest.mark.parametrize("backend",["dynamodb","unknown"])
def test_unavailable_backends_fail_closed_without_sqlite_fallback(backend,tmp_path,monkeypatch):
 monkeypatch.chdir(tmp_path)
 with pytest.raises(AdsStorageConfigurationError) as error:create_ads_repository(backend)
 assert "secret" not in str(error.value).lower() and not (tmp_path/"data"/"amazon_ai_agent.db").exists()

def test_lambda_persistence_requirement_blocks_sqlite():
 with pytest.raises(AdsStorageConfigurationError,match="requires persistent Ads storage"):create_ads_repository("sqlite",require_persistent=True)
