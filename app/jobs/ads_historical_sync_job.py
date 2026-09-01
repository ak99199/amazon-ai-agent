"""Trusted callable entrypoint; never invoked automatically."""
from datetime import datetime,timezone
from os import getenv
from app.amazon_ads.auth import AdsLwaAuthenticator
from app.amazon_ads.client import AmazonAdsClient
from app.amazon_ads.config import AdsScheduledSyncConfig,AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.report_transport import AdsReportTransport
from app.amazon_ads.reporting import SponsoredProductsReportingService
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_historical_sync_execution_service import AdsHistoricalSyncExecutionService
from app.services.ads_live_report_download_validation_service import AdsLiveReportDownloadValidationService
from app.services.ads_live_report_lifecycle_validation_service import AdsLiveReportLifecycleValidationService
from app.services.ads_live_report_persistence_service import AdsLiveReportPersistenceService
from app.services.ads_production_readiness_service import AdsProductionReadinessService
from app.services.ads_scheduled_historical_sync_service import AdsScheduledHistoricalSyncService

def run_scheduled_ads_historical_sync(service=None,seller_id=None,marketplace_id=None):
 if service is None:
  now=lambda:datetime.now(timezone.utc);settings=AdsSettings.from_environment();readiness=AdsProductionReadinessService(settings,AdsLiveReadConfig.from_environment());repository=AdsPerformanceRepository();seller_id=seller_id or getenv("AMAZON_SELLER_ID");marketplace_id=marketplace_id or getenv("AMAZON_MARKETPLACE_ID")
  def execution_factory():
   reporting=SponsoredProductsReportingService()
   def dependencies():client=AmazonAdsClient(settings,AdsLwaAuthenticator(settings));return AdsReportTransport(client,max_attempts=1),reporting
   lifecycle=AdsLiveReportLifecycleValidationService(readiness,dependencies,max_polls=5);download=AdsLiveReportDownloadValidationService(lifecycle,reporting,row_limit=100,compressed_limit=1048576,decompressed_limit=5242880);persistence=AdsLiveReportPersistenceService(download,repository,seller_id,marketplace_id);return AdsHistoricalSyncExecutionService(repository,persistence,now)
  service=AdsScheduledHistoricalSyncService(AdsScheduledSyncConfig.from_environment(),readiness,repository,execution_factory,now)
 return service.run(seller_id,marketplace_id).public_dict()
