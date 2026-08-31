from datetime import datetime,timezone,timedelta
from app.amazon.models import Listing
from app.database.repository import ListingSnapshotRepository

def listing(seller="seller-a",marketplace="market-a",price="10",title="Title",status="ACTIVE"):
    return Listing(seller,marketplace,"SKU","B012345678",title=title,price=price,currency="INR",listing_status=status)
def repo(tmp_path): return ListingSnapshotRepository(tmp_path/"test.db")
def test_first_snapshot_and_latest(tmp_path):
    storage=repo(tmp_path); saved=storage.save_listing_snapshot(listing())
    assert saved.changed and storage.get_latest_listing("seller-a","market-a","B012345678").id == saved.id
def test_unchanged_snapshot_detection(tmp_path):
    storage=repo(tmp_path); storage.save_listing_snapshot(listing()); saved=storage.save_listing_snapshot(listing())
    assert not saved.changed
def test_meaningful_changes(tmp_path):
    storage=repo(tmp_path); storage.save_listing_snapshot(listing()); assert storage.save_listing_snapshot(listing(price="11")).changed; assert storage.save_listing_snapshot(listing(title="New")).changed; assert storage.save_listing_snapshot(listing(status="INACTIVE")).changed
def test_history_limit_and_isolation(tmp_path):
    storage=repo(tmp_path)
    for price in ("1","2","3"): storage.save_listing_snapshot(listing(price=price))
    storage.save_listing_snapshot(listing(seller="seller-b")); storage.save_listing_snapshot(listing(marketplace="market-b"))
    assert len(storage.get_listing_history("seller-a","market-a","B012345678",2)) == 2
    assert storage.count_snapshots("seller-a","market-a") == 3
    assert storage.count_snapshots("seller-b","market-a") == 1
    assert storage.count_snapshots("seller-a","market-b") == 1
def test_changed_query_and_empty_history(tmp_path):
    storage=repo(tmp_path); now=datetime.now(timezone.utc); storage.save_listing_snapshot(listing(),now)
    assert len(storage.find_changed_listings("seller-a","market-a",now-timedelta(seconds=1))) == 1
    assert storage.get_listing_history("seller-a","market-a","UNKNOWN") == []
