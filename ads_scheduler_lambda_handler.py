"""Build-ready AWS Lambda adapter for trusted scheduled Ads synchronization."""
from app.amazon_ads.config import AdsScheduledSyncConfig
from app.database.ads_base import AdsStorageConfigurationError,create_ads_repository
from app.jobs.ads_historical_sync_job import run_scheduled_ads_historical_sync

_SAFE_FIELDS=("status","run_id","rows_persisted","message","error_code")

def _safe_result(result):
    return {name:result.get(name) for name in _SAFE_FIELDS if name in result}

def handler(event,context):
    del event,context
    try:
        if not AdsScheduledSyncConfig.from_environment().enabled:
            return {"status":"disabled","run_id":None,"rows_persisted":0,"message":"Scheduled historical sync is disabled."}
        create_ads_repository(require_persistent=True)
        return _safe_result(run_scheduled_ads_historical_sync())
    except AdsStorageConfigurationError:
        return {"status":"storage_blocked","run_id":None,"rows_persisted":0,"message":"Scheduled Amazon Ads Lambda execution requires persistent Ads storage."}
    except Exception:
        return {"status":"unavailable","run_id":None,"rows_persisted":0,"message":"Scheduled Amazon Ads Lambda execution is unavailable."}
