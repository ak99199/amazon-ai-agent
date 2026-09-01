"""Build-ready AWS Lambda adapter for trusted scheduled Ads synchronization."""
from os import getenv
from app.amazon_ads.config import AdsScheduledSyncConfig,AdsSettings
from app.aws.secrets import SecretLoadError,load_ads_secret
from app.database.ads_base import AdsStorageConfigurationError,create_ads_repository
from app.jobs.ads_historical_sync_job import run_scheduled_ads_historical_sync

_SAFE_FIELDS=("status","run_id","rows_persisted","message","error_code")

def _safe_result(result):
    return {name:result.get(name) for name in _SAFE_FIELDS if name in result}

def _secrets_client():
    import boto3
    return boto3.client("secretsmanager")

def handler(event,context):
    del event,context
    try:
        if not AdsScheduledSyncConfig.from_environment().enabled:
            return {"status":"disabled","run_id":None,"rows_persisted":0,"message":"Scheduled historical sync is disabled."}
        repository=create_ads_repository(require_persistent=True)
        secret_arn=(getenv("AMAZON_ADS_SECRET_ARN") or "").strip()
        if not secret_arn:return {"status":"readiness_blocked","run_id":None,"rows_persisted":0,"message":"Scheduled Amazon Ads credentials are not configured."}
        secret=load_ads_secret(secret_arn,_secrets_client())
        settings=AdsSettings(secret["AMAZON_ADS_CLIENT_ID"],secret["AMAZON_ADS_CLIENT_SECRET"],secret["AMAZON_ADS_REFRESH_TOKEN"],getenv("AMAZON_ADS_PROFILE_ID") or None,(getenv("AMAZON_ADS_REGION") or "FE").upper())
        return _safe_result(run_scheduled_ads_historical_sync(repository=repository,settings=settings))
    except AdsStorageConfigurationError:
        return {"status":"storage_blocked","run_id":None,"rows_persisted":0,"message":"Scheduled Amazon Ads Lambda execution requires persistent Ads storage."}
    except SecretLoadError:
        return {"status":"unavailable","run_id":None,"rows_persisted":0,"message":"Scheduled Amazon Ads credentials are unavailable."}
    except Exception:
        return {"status":"unavailable","run_id":None,"rows_persisted":0,"message":"Scheduled Amazon Ads Lambda execution is unavailable."}
