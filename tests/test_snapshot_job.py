from app.amazon.listings import ListingPage
from app.amazon.models import Listing
from app.jobs import listing_snapshot_job
from app.services.snapshot_collector import CollectionResult
from datetime import datetime,timezone
class Collector:
    def collect(self,*args): return CollectionResult(datetime.now(timezone.utc),datetime.now(timezone.utc),1,1,1,0,0,1,True,())
def test_job_is_reusable(monkeypatch):
    class Settings:
        seller_id="seller"; marketplace_id="market"
        def require_complete(self): return self
    monkeypatch.setattr(listing_snapshot_job.Settings,"from_environment",lambda: Settings())
    monkeypatch.setattr(listing_snapshot_job,"SnapshotCollector",lambda *args: Collector())
    assert listing_snapshot_job.run_listing_snapshot_job(2,5).snapshots_saved == 1
