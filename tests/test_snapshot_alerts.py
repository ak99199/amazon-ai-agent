from datetime import datetime,timedelta,timezone
from app.amazon.models import Listing
from app.alerts.repository import SQLiteAlertRepository
from app.database.repository import ListingSnapshotRepository
from app.jobs import listing_snapshot_job
from app.services.snapshot_collector import CollectionResult

def result(success=True):
    now=datetime.now(timezone.utc);return CollectionResult(now,now,1,1,1,0,0,1,success,())
class Settings:
    seller_id="seller";marketplace_id="market"
    def require_complete(self):return self
class Collector:
    def __init__(self,*args):pass
    def collect(self,*args):return result()
def test_successful_snapshot_job_runs_alert_evaluator(monkeypatch):
    calls=[];monkeypatch.setenv("ALERTS_ENABLED","true");monkeypatch.setattr(listing_snapshot_job,"SnapshotCollector",Collector)
    output=listing_snapshot_job.run_listing_snapshot_job(settings=Settings(),alert_evaluator=lambda *args:calls.append(args))
    assert output.success and len(calls)==1 and calls[0][1:3]==("seller","market")
def test_disabled_alerts_skip_evaluation(monkeypatch):
    calls=[];monkeypatch.delenv("ALERTS_ENABLED",raising=False);monkeypatch.setattr(listing_snapshot_job,"SnapshotCollector",Collector)
    listing_snapshot_job.run_listing_snapshot_job(settings=Settings(),alert_evaluator=lambda *args:calls.append(args))
    assert calls==[]
def test_alert_failure_does_not_change_successful_collection(monkeypatch,caplog):
    monkeypatch.setenv("ALERTS_ENABLED","true");monkeypatch.setattr(listing_snapshot_job,"SnapshotCollector",Collector)
    def broken(*args):raise RuntimeError("refresh-token")
    output=listing_snapshot_job.run_listing_snapshot_job(settings=Settings(),alert_evaluator=broken)
    assert output.success and "refresh-token" not in caplog.text and "RuntimeError" in caplog.text
def test_changed_snapshot_alerts_are_deduplicated(tmp_path,monkeypatch):
    monkeypatch.setenv("ALERTS_ENABLED","true");snapshots=ListingSnapshotRepository(tmp_path/"snapshots.db");alerts=SQLiteAlertRepository(tmp_path/"alerts.db");start=datetime.now(timezone.utc)-timedelta(seconds=1)
    snapshots.save_listing_snapshot(Listing("seller","market","SKU","B012345678",listing_status="INACTIVE"))
    first=listing_snapshot_job.evaluate_snapshot_alerts(snapshots,"seller","market",start,alerts)
    stored_after_first=alerts.list_alerts("seller","market")
    second=listing_snapshot_job.evaluate_snapshot_alerts(snapshots,"seller","market",start,alerts)
    stored_after_second=alerts.list_alerts("seller","market")
    assert first==3 and second==0
    assert {alert.alert_type for alert in stored_after_first} == {"LISTING_INACTIVE","PRIORITY_RECOMMENDATION","RECENT_MAJOR_CHANGE"}
    assert len({alert.dedupe_key for alert in stored_after_first}) == first
    assert len(stored_after_second) == len(stored_after_first) == first
def test_no_amazon_write_operations_are_used(monkeypatch):
    monkeypatch.setenv("ALERTS_ENABLED","true");monkeypatch.setattr(listing_snapshot_job,"SnapshotCollector",Collector)
    assert listing_snapshot_job.run_listing_snapshot_job(settings=Settings(),alert_evaluator=lambda *args:0).success