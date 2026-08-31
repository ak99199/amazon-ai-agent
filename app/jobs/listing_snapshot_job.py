"""Composable runner for one complete read-only collection cycle."""
import logging
from app.alerts.providers import alerts_enabled,notification_provider_from_environment
from app.alerts.repository import create_alert_repository
from app.config import Settings
from app.amazon.auth import LwaAuthenticator
from app.amazon.client import AmazonSPAPIClient
from app.amazon.listings import AmazonListingsService
from app.database.repository import ListingSnapshotRepository
from app.services.alert_service import AlertService
from app.services.listing_intelligence_service import ListingIntelligenceService
from app.services.listing_recommendation_service import ListingRecommendationService
from app.services.listing_service import ListingService
from app.services.snapshot_collector import SnapshotCollector
logger=logging.getLogger(__name__)

def evaluate_snapshot_alerts(snapshot_repository,seller_id,marketplace_id,since_timestamp,alert_repository=None,alert_service=None):
    """Evaluate deterministic alerts for listings changed during one completed run."""
    if not alerts_enabled(): return 0
    repository=alert_repository or create_alert_repository();service=alert_service or AlertService(repository,notification_provider_from_environment());intelligence=ListingIntelligenceService(snapshot_repository);recommendations=ListingRecommendationService();asins=sorted({snapshot.asin for snapshot in snapshot_repository.find_changed_listings(seller_id,marketplace_id,since_timestamp)})
    stored=0
    for asin in asins:
        latest=snapshot_repository.get_latest_listing(seller_id,marketplace_id,asin)
        if not latest: continue
        insight=intelligence.analyze(seller_id,marketplace_id,asin,"30")
        normalized={"seller_id":seller_id,"marketplace_id":marketplace_id,"asin":asin,"current_listing":{"listing_status":latest.listing_status},"intelligence":insight.public_dict(),"recommendations":recommendations.recommend(insight).public_dict()}
        stored+=len(service.process(normalized))
    return stored

def run_listing_snapshot_job(max_pages=100,page_size=10,settings=None,repository=None,alert_evaluator=None):
    settings=(settings or Settings.from_environment()).require_complete();repository=repository or ListingSnapshotRepository();listings=ListingService(AmazonListingsService(AmazonSPAPIClient(LwaAuthenticator(settings))));result=SnapshotCollector(listings,repository).collect(settings.seller_id or "",settings.marketplace_id or "",page_size,max_pages)
    if result.success and alerts_enabled():
        try:
            (alert_evaluator or evaluate_snapshot_alerts)(repository,settings.seller_id or "",settings.marketplace_id or "",result.started_at)
        except Exception as error:
            logger.warning("snapshot alert evaluation failed error_type=%s",type(error).__name__)
    return result