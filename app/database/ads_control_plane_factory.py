"""Fail-closed Ads control-plane repository selection."""
import os
from app.database.ads_repository import AdsPerformanceRepository
from app.database.ads_control_plane_dynamodb_repository import DynamoDbAdsControlPlaneRepository


class AdsControlPlaneConfigurationError(RuntimeError):pass


def create_ads_control_plane_repository(database_path=None,dynamodb_resource=None,dynamodb_client=None):
    backend=os.getenv("AMAZON_ADS_CONTROL_PLANE_BACKEND","sqlite").strip().lower()
    if backend=="sqlite":return AdsPerformanceRepository(database_path) if database_path is not None else AdsPerformanceRepository()
    if backend!="dynamodb":raise AdsControlPlaneConfigurationError("Unsupported Ads control-plane backend")
    table_name=os.getenv("AMAZON_ADS_DYNAMODB_CONTROL_PLANE_TABLE","").strip()
    if not table_name:raise AdsControlPlaneConfigurationError("Ads control-plane table is required")
    try:
        if dynamodb_resource is None:
            import boto3
            dynamodb_resource=boto3.resource("dynamodb")
        table=dynamodb_resource.Table(table_name)
        client=dynamodb_client or getattr(getattr(table,"meta",None),"client",None) or getattr(dynamodb_resource,"meta",None).client
        return DynamoDbAdsControlPlaneRepository(table,client,table_name)
    except AdsControlPlaneConfigurationError:raise
    except Exception as error:raise AdsControlPlaneConfigurationError("Ads control-plane storage is unavailable") from error
