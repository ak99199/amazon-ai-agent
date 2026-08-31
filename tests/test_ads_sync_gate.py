from datetime import datetime, timezone, date, timedelta
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_sync_gate_service import AdsSyncGateService

def gate(tmp_path,config,approval="pending"):
 now=lambda:datetime(2026,1,10,tzinfo=timezone.utc)
 return AdsSyncGateService(AdsSettings("id","secret","refresh","profile"),AdsPerformanceRepository(tmp_path/"ads.db"),config,approval,now,cooldown_seconds=60)
def test_sync_gate_blocks_live_and_allows_mock(tmp_path):
 assert gate(tmp_path,AdsLiveReadConfig(True,False),"pending").evaluate("s","m").status_code=="blocked_approval"
 assert gate(tmp_path,AdsLiveReadConfig(False,True)).evaluate("s","m").status_code=="allowed_mock"
def test_sync_gate_bounds_dates_active_and_cooldown(tmp_path):
 service=gate(tmp_path,AdsLiveReadConfig(False,True));assert service.evaluate("s","m",window_days=91).status_code=="blocked_window_too_large"
 repository=service.repository;now=datetime(2026,1,10,tzinfo=timezone.utc)
 repository.save_sync_run(AdsManualSyncResult("active","mock","s","m","profile",date(2026,1,9),date(2026,1,10),now,None,False,"running"))
 assert service.evaluate("s","m").status_code=="blocked_in_progress"
