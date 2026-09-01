"""Amazon Ads repository selection, separate from listing snapshot storage."""
from os import getenv

class AdsStorageConfigurationError(Exception):
    pass

def create_ads_repository(backend=None,require_persistent=False):
    mode=(getenv("AMAZON_ADS_STORAGE_BACKEND","sqlite") if backend is None else backend).strip().lower()
    if mode=="sqlite":
        if require_persistent:
            raise AdsStorageConfigurationError("Scheduled Amazon Ads Lambda execution requires persistent Ads storage.")
        from app.database.ads_repository import AdsPerformanceRepository
        return AdsPerformanceRepository()
    if mode=="dynamodb":
        raise AdsStorageConfigurationError("Persistent Amazon Ads storage backend is not available.")
    raise AdsStorageConfigurationError("Amazon Ads storage backend is not configured.")
