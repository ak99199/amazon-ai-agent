from datetime import datetime,timezone,date
from decimal import Decimal
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.ingestion_models import AdsIngestionResult
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_diagnostics_service import AdsDiagnosticsService
from app.services.ads_readiness_service import AdsReadinessService
SENTINELS=("TEST_CLIENT_ID_123","TEST_CLIENT_SECRET_456","TEST_REFRESH_TOKEN_789","TEST_PROFILE_ID_001")
def settings(profile=None):return AdsSettings(SENTINELS[0],SENTINELS[1],SENTINELS[2],profile,"FE")
def result(success=True,run_id="run"):
 now=datetime(2026,1,1,tzinfo=timezone.utc);return AdsIngestionResult(run_id,now,now,0,0,0,0,0,0,0,success,())
def test_readiness_precedence_and_redaction(tmp_path):
 diagnostics=AdsDiagnosticsService(AdsPerformanceRepository(tmp_path/"a.db"));pending=AdsReadinessService(diagnostics,settings(),"pending").get("s","m");payload=pending.public_dict()
 assert pending.overall_status=="approval_pending"
 for key in ("has_client_id","has_client_secret","has_refresh_token","has_profile_id"):assert key in payload
 assert payload["has_client_id"] and payload["has_client_secret"] and payload["has_refresh_token"] and not payload["has_profile_id"]
 for value in SENTINELS:assert value not in str(payload)
 for key in ("client_id","client_secret","refresh_token","access_token","authorization"):assert key not in payload
 assert AdsReadinessService(diagnostics,AdsSettings(None,None,None,None,"FE"),"approved").get("s","m").overall_status=="configuration_incomplete"
 assert AdsReadinessService(diagnostics,settings(),"approved").get("s","m").overall_status=="profile_not_selected"
 assert AdsReadinessService(diagnostics,settings(SENTINELS[3]),"invalid").get("s","m").approval_status=="unknown"
def test_diagnostics_scope_and_ready_state(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"a.db");repo.save_ingestion_run(result(),"s","m","p");repo.save_ingestion_run(result(False,"other-run"),"other","m","p");repo.save(AdsPerformanceDaily("s","m","p",date(2026,1,1),"SP",impressions=1,clicks=1,spend=Decimal("1"),orders=1,units=1,sales=Decimal("2")))
 value=AdsDiagnosticsService(repo).get("s","m","p");ready=AdsReadinessService(AdsDiagnosticsService(repo),settings("p"),"approved").get("s","m")
 assert value["ingestion_run_count"]==1 and value["successful_run_count"]==1 and value["latest_run_status"]=="success" and value["earliest_data_date"]=="2026-01-01" and ready.overall_status=="ready"