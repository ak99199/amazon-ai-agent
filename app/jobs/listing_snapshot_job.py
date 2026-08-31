"""Composable runner for one complete read-only collection cycle."""
from app.config import Settings
from app.amazon.auth import LwaAuthenticator
from app.amazon.client import AmazonSPAPIClient
from app.amazon.listings import AmazonListingsService
from app.database.repository import ListingSnapshotRepository
from app.services.listing_service import ListingService
from app.services.snapshot_collector import SnapshotCollector
def run_listing_snapshot_job(max_pages=100,page_size=10):
    settings=Settings.from_environment().require_complete(); listings=ListingService(AmazonListingsService(AmazonSPAPIClient(LwaAuthenticator(settings)))); collector=SnapshotCollector(listings,ListingSnapshotRepository()); return collector.collect(settings.seller_id or "",settings.marketplace_id or "",page_size,max_pages)
