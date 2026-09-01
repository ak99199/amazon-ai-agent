"""Amazon Ads repository selection, separate from listing snapshot storage."""
from os import getenv

class AdsStorageConfigurationError(Exception):
    pass

def create_ads_repository(backend=None,require_persistent=False,dynamodb_resource=None,dynamodb_client=None):
    mode=(getenv("AMAZON_ADS_STORAGE_BACKEND","sqlite") if backend is None else backend).strip().lower()
    if mode=="sqlite":
        if require_persistent:
            raise AdsStorageConfigurationError("Scheduled Amazon Ads Lambda execution requires persistent Ads storage.")
        from app.database.ads_repository import AdsPerformanceRepository
        return AdsPerformanceRepository()
    if mode=="dynamodb":
        performance=getenv("AMAZON_ADS_DYNAMODB_PERFORMANCE_TABLE");runs=getenv("AMAZON_ADS_DYNAMODB_SYNC_RUNS_TABLE")
        if not performance or not runs:raise AdsStorageConfigurationError("Persistent Amazon Ads storage is not configured.")
        if dynamodb_resource is None:
            try:
                import boto3
                dynamodb_resource=boto3.resource("dynamodb")
            except Exception:raise AdsStorageConfigurationError("Persistent Amazon Ads storage support is unavailable.") from None
        try:
            from app.database.ads_dynamodb_repository import DynamoDbAdsHistoricalRepository
            return DynamoDbAdsHistoricalRepository(dynamodb_resource.Table(performance),dynamodb_resource.Table(runs),dynamodb_client)
        except AdsStorageConfigurationError:raise
        except Exception:raise AdsStorageConfigurationError("Persistent Amazon Ads storage is unavailable.") from None
    raise AdsStorageConfigurationError("Amazon Ads storage backend is not configured.")
