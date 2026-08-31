from datetime import datetime,timezone,timedelta
from app.amazon.models import Listing
from app.database.repository import ListingSnapshotRepository
from app.services.listing_history_service import ListingHistoryService

def item(price,title,status): return Listing("seller","market","SKU","B012345678",title=title,price=price,currency="INR",listing_status=status)
def test_trend_calculations(tmp_path):
    service=ListingHistoryService(ListingSnapshotRepository(tmp_path/"history.db")); start=datetime(2026,1,1,tzinfo=timezone.utc)
    service._repository.save_listing_snapshot(item("10","Old","ACTIVE"),start); service._repository.save_listing_snapshot(item("15","New","INACTIVE"),start+timedelta(days=3))
    trend=service.get_trend("seller","market","B012345678")
    assert trend.price_change == "5" and trend.title_changed and trend.status_changed and trend.number_of_snapshots == 2 and trend.days_tracked == 3
def test_empty_trend(tmp_path):
    trend=ListingHistoryService(ListingSnapshotRepository(tmp_path/"history.db")).get_trend("seller","market","NONE")
    assert trend.number_of_snapshots == 0 and trend.first_seen is None
def test_explicit_snapshot_persistence(tmp_path):
    service=ListingHistoryService(ListingSnapshotRepository(tmp_path/"history.db"))
    saved=service.save_current_listings([item("10","Title","ACTIVE")])
    assert len(saved) == 1 and saved[0].changed
