from app.amazon.listings import ListingPage
from app.amazon.models import Listing
from app.database.repository import ListingSnapshotRepository
from app.services.snapshot_collector import SnapshotCollector
class Pages:
    def __init__(self,pages): self.pages=iter(pages); self.calls=[]
    def get_listings(self,*args): self.calls.append(args); value=next(self.pages); return value
class BrokenRepository(ListingSnapshotRepository):
    def save_listing_snapshot(self,listing):
        if listing.sku == "BAD": raise ValueError("secret should not leak")
        return super().save_listing_snapshot(listing)
def item(sku="SKU",price="10"): return Listing("seller","market",sku,"B012345678",price=price)
def test_single_page_collection_and_metadata(tmp_path):
    repo=ListingSnapshotRepository(tmp_path/"db.sqlite"); result=SnapshotCollector(Pages([ListingPage([item()],None)]),repo).collect("seller","market")
    assert result.success and result.listings_fetched == result.snapshots_saved == result.changed_count == result.pages_processed == 1 and repo.count_snapshot_runs() == 1
def test_multi_page_and_max_pages(tmp_path):
    repo=ListingSnapshotRepository(tmp_path/"db.sqlite"); pages=Pages([ListingPage([item("A")],"next"),ListingPage([item("B")],None)])
    result=SnapshotCollector(pages,repo).collect("seller","market",max_pages=1)
    assert result.pages_processed == 1 and result.listings_fetched == 1 and len(pages.calls) == 1
def test_unchanged_and_individual_failure_are_isolated(tmp_path):
    repo=BrokenRepository(tmp_path/"db.sqlite"); first=SnapshotCollector(Pages([ListingPage([item()],None)]),repo).collect("seller","market"); result=SnapshotCollector(Pages([ListingPage([item(),item("BAD")],None)]),repo).collect("seller","market")
    assert first.changed_count == 1 and result.unchanged_count == 1 and result.failed_count == 1 and "secret" not in str(result.errors)
def test_page_failure_is_safe(tmp_path):
    class Failed:
        def get_listings(self,*args): raise RuntimeError("access-token")
    result=SnapshotCollector(Failed(),ListingSnapshotRepository(tmp_path/"db.sqlite")).collect("seller","market")
    assert not result.success and result.pages_processed == 0 and "access-token" not in str(result.errors)
