"""AWS Lambda entry point for read-only listing snapshot collection."""
import logging,os
from app.aws.secrets import SecretLoadError,load_sp_api_secret
from app.config import ConfigurationError,Settings
from app.database.dynamodb_repository import DynamoDbSnapshotRepository
from app.jobs.listing_snapshot_job import run_listing_snapshot_job
logger=logging.getLogger(__name__)
def _value(event,name,default,minimum,maximum):
    value=(event or {}).get(name,default)
    if isinstance(value,bool) or not isinstance(value,int) or value<minimum or value>maximum: return default
    return value
def lambda_handler(event,context):
    try:
        if os.getenv("STORAGE_BACKEND","sqlite") != "dynamodb": raise ConfigurationError("Cloud storage is not configured")
        secret_arn=os.getenv("SECRET_ARN"); seller_id=os.getenv("SELLER_ID"); marketplace_id=os.getenv("MARKETPLACE_ID"); snapshots=os.getenv("DYNAMODB_SNAPSHOTS_TABLE"); runs=os.getenv("DYNAMODB_RUNS_TABLE")
        if not all((secret_arn,seller_id,marketplace_id,snapshots,runs)): raise ConfigurationError("Cloud storage is not configured")
        import boto3
        secret=load_sp_api_secret(secret_arn,boto3.client("secretsmanager")); settings=Settings(secret["SP_API_CLIENT_ID"],secret["SP_API_CLIENT_SECRET"],secret["SP_API_REFRESH_TOKEN"],seller_id,marketplace_id); dynamodb=boto3.resource("dynamodb"); repository=DynamoDbSnapshotRepository(dynamodb.Table(snapshots),dynamodb.Table(runs)); result=run_listing_snapshot_job(_value(event,"max_pages",100,1,100),_value(event,"page_size",10,1,20),settings,repository); return result.public_dict()
    except (ConfigurationError,SecretLoadError) as error:
        logger.warning("snapshot lambda configuration failed error_type=%s",type(error).__name__); return {"success":False,"listings_fetched":0,"snapshots_saved":0,"changed_count":0,"unchanged_count":0,"failed_count":0,"pages_processed":0,"errors":["snapshot collection could not start"]}
    except Exception as error:
        logger.exception("snapshot lambda failed error_type=%s",type(error).__name__); return {"success":False,"listings_fetched":0,"snapshots_saved":0,"changed_count":0,"unchanged_count":0,"failed_count":0,"pages_processed":0,"errors":["snapshot collection failed"]}
