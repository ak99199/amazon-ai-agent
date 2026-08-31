from datetime import date, datetime, timedelta, timezone
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_sync_gate_service import AdsSyncGateService
from app.services.ads_sync_observability_service import AdsSyncObservabilityService
def run(id,status,success,now):return AdsManualSyncResult(id,"mock","s","m","p",date(2026,1,1),date(2026,1,1),now,now,success,status,rows_saved=2,rows_failed=1,error_code=None if success else "remote_error",safe_error_message=None if success else "safe")
def test_observability_never_synced_healthy_and_failing(tmp_path):
 base = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
 now = lambda: base + timedelta(minutes=3)
 repo = AdsPerformanceRepository(tmp_path / "a.db")
 gate = AdsSyncGateService(AdsSettings("i", "s", "r", "p"), repo, AdsLiveReadConfig(False, True), now=now, cooldown_seconds=0)
 svc = AdsSyncObservabilityService(repo, gate, now)
 assert svc.get("s", "m").health_status == "never_synced"
 repo.save_sync_run(run("ok", "completed", True, base))
 assert svc.get("s", "m").health_status == "healthy"
 repo.save_sync_run(run("bad1", "failed", False, base + timedelta(minutes=1)))
 assert svc.get("s", "m").health_status == "degraded"
 repo.save_sync_run(run("bad2", "failed", False, base + timedelta(minutes=2)))
 assert svc.get("s", "m").health_status == "failing"

def test_sync_runs_with_equal_timestamps_have_deterministic_order(tmp_path):
 timestamp = datetime(2026, 1, 10, tzinfo=timezone.utc)
 repo = AdsPerformanceRepository(tmp_path / "a.db")
 repo.save_sync_run(run("older-id", "completed", True, timestamp))
 repo.save_sync_run(run("newer-id", "failed", False, timestamp))
 assert repo.latest_sync_run("s", "m", "p")["sync_id"] == "newer-id"
 assert [item.sync_id for item in repo.list_sync_runs("s", "m", "p")] == ["newer-id", "older-id"]
 assert repo.latest_failed_sync("s", "m", "p").sync_id == "newer-id"
