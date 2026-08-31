from datetime import datetime, timezone
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_manual_sync_service import AdsManualSyncService
from app.services.ads_sync_gate_service import AdsSyncGateService

def test_manual_mock_sync_is_persisted_and_blocked_gate_does_not_run(tmp_path):
 repository=AdsPerformanceRepository(tmp_path/"ads.db");now=lambda:datetime(2026,1,10,tzinfo=timezone.utc)
 gate=AdsSyncGateService(AdsSettings("id","secret","refresh","profile"),repository,AdsLiveReadConfig(False,True),now=now,cooldown_seconds=0);calls=[]
 service=AdsManualSyncService(gate,repository,runner=lambda *args:(calls.append(args) or {"rows_saved":2}),now=now)
 result=service.run("s","m");assert result.success and result.rows_saved==2 and len(calls)==1
 blocked=AdsManualSyncService(AdsSyncGateService(AdsSettings("id","secret","refresh","profile"),repository,AdsLiveReadConfig(True,False),"pending",now,0),repository,runner=lambda *args:(_ for _ in ()).throw(Exception("network")),now=now)
 assert blocked.run("s","m").status_code=="blocked_approval"
