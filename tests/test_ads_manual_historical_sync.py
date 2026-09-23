from datetime import date,datetime,timezone

import pytest

from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_models import AdsLiveReportStatus
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.reporting import SponsoredProductsReportingService
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_historical_sync_execution_service import HISTORICAL_SYNC_MODE,VALIDATION_SYNC_MODE
from app.services.ads_live_report_download_validation_service import AdsLiveReportDownloadValidationService
from app.services.ads_live_report_lifecycle_validation_service import AdsLiveReportLifecycleValidationService
from app.services.ads_live_report_persistence_service import AdsLiveReportPersistenceService
from app.services.ads_manual_historical_sync_service import AdsManualHistoricalSyncService
from app.services.ads_production_readiness_service import AdsProductionReadinessService
from app.services.ads_sync_gate_service import AdsSyncGateService

NOW=datetime(2026,2,10,12,tzinfo=timezone.utc)

def report_row():return {"date":"2026-02-08","campaignId":"c1","impressions":"10","clicks":"2","cost":"1.25","purchases14d":"1","unitsSoldClicks14d":"1","sales14d":"4.50"}
def readiness():return AdsProductionReadinessService(AdsSettings("id","secret","refresh","profile","FE"),AdsLiveReadConfig(True,False),"approved")

class Transport:
 def __init__(self,repository,statuses=(),rows=None):self.repository=repository;self.statuses=list(statuses);self.rows=[report_row()] if rows is None else rows;self.creates=[];self.checks=[];self.downloads=[]
 def create(self,profile,definition):
  assert self.repository.active_sync_run("seller","market",profile) is not None
  self.creates.append((profile,definition));return "internal-report-id"
 def status(self,profile,report_id):
  self.checks.append((profile,report_id));return AdsLiveReportStatus(report_id,self.statuses.pop(0),"https://signed-secret")
 def download_gzip_json(self,location,*limits):self.downloads.append((location,limits));return self.rows,100,200

def service(tmp_path,transport=None,mode=HISTORICAL_SYNC_MODE,download=True,persist=True,repository=None):
 repository=repository or AdsPerformanceRepository(tmp_path/"ads.db");transport=transport or Transport(repository);ready=readiness();reporting=SponsoredProductsReportingService()
 dependencies=lambda:(transport,reporting)
 lifecycle=AdsLiveReportLifecycleValidationService(ready,dependencies,now=lambda:NOW,sleeper=lambda _:None)
 validator=AdsLiveReportDownloadValidationService(lifecycle,reporting)
 persistence_service=AdsLiveReportPersistenceService(validator,repository,"seller","market")
 gate=AdsSyncGateService(ready.settings,repository,ready.config,ready.approval_status,lambda:NOW,cooldown_seconds=60)
 return AdsManualHistoricalSyncService(ready,gate,repository,persistence_service,lambda:NOW,dependency_factory=dependencies,mode=mode,trigger_source="manual" if persist else "validation",download=download,persist=persist),repository,transport

def test_create_is_reserved_saved_once_and_never_public(tmp_path):
 svc,repo,transport=service(tmp_path);result=svc.run("seller","market",True);active=repo.active_sync_run("seller","market","profile")
 assert result.status=="pending" and len(transport.creates)==1 and transport.checks==[]
 assert active.report_id=="internal-report-id" and active.amazon_report_status=="pending" and active.report_type_id=="spCampaigns"
 assert "report_id" not in result.public_dict() and "internal-report-id" not in str(result.public_dict())

def test_pending_resumes_same_report_keeps_lock_and_updates_check(tmp_path):
 svc,repo,transport=service(tmp_path);transport.statuses=["pending"]
 first=svc.run("seller","market",True);second=svc.run("seller","market",True);active=repo.active_sync_run("seller","market","profile")
 assert first.run_id==second.run_id and second.status=="pending" and len(transport.creates)==1
 assert transport.checks==[("profile","internal-report-id")] and active.sync_id==first.run_id and active.report_last_checked_at==NOW and active.report_claim is None

def test_completed_manual_sync_downloads_persists_finalizes_once(tmp_path):
 svc,repo,transport=service(tmp_path);transport.statuses=["completed"]
 svc.run("seller","market",True);result=svc.run("seller","market",True);again=svc.run("seller","market",True)
 assert result.status=="succeeded" and result.rows_persisted==1 and len(transport.downloads)==1
 assert repo.count_performance_rows("seller","market","profile")==1 and repo.active_sync_run("seller","market","profile") is None
 assert again.status=="cooldown_active" and len(transport.creates)==1 and len(transport.downloads)==1

def test_validation_lifecycle_and_download_reuse_report_without_persistence(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");transport=Transport(repo,["pending","completed"])
 lifecycle,_,_=service(tmp_path,transport,VALIDATION_SYNC_MODE,False,False,repo);download,_,_=service(tmp_path,transport,VALIDATION_SYNC_MODE,True,False,repo)
 created=lifecycle.run("seller","market",True);pending=lifecycle.run("seller","market",True);completed=download.run("seller","market",True)
 assert created.run_id==pending.run_id==completed.run_id and pending.status=="pending" and completed.status=="validation_succeeded"
 assert len(transport.creates)==1 and len(transport.downloads)==1 and repo.count_performance_rows("seller","market","profile")==0
 assert repo.latest_successful_sync("seller","market","profile",HISTORICAL_SYNC_MODE) is None

def test_completed_lifecycle_is_download_ready_without_downloading_or_releasing(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");transport=Transport(repo,["completed"]);lifecycle,_,_=service(tmp_path,transport,VALIDATION_SYNC_MODE,False,False,repo)
 lifecycle.run("seller","market",True);result=lifecycle.run("seller","market",True)
 assert result.status=="download_ready" and transport.downloads==[] and repo.active_sync_run("seller","market","profile").sync_id==result.run_id

def test_download_validation_pending_never_downloads(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");transport=Transport(repo,["pending"]);download,_,_=service(tmp_path,transport,VALIDATION_SYNC_MODE,True,False,repo)
 download.run("seller","market",True);result=download.run("seller","market",True)
 assert result.status=="pending" and transport.downloads==[] and repo.active_sync_run("seller","market","profile") is not None

@pytest.mark.parametrize("status",["failed","cancelled"])
def test_terminal_amazon_failure_releases_lock_without_persistence(tmp_path,status):
 svc,repo,transport=service(tmp_path);transport.statuses=[status]
 svc.run("seller","market",True);result=svc.run("seller","market",True)
 assert result.status=="failed" and result.error_code=="report_failed" and repo.active_sync_run("seller","market","profile") is None
 assert transport.downloads==[] and repo.count_performance_rows("seller","market","profile")==0

def test_creating_without_report_id_never_recreates(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");run=AdsManualSyncResult("run",HISTORICAL_SYNC_MODE,"seller","market","profile",date(2026,2,8),date(2026,2,9),NOW,None,False,"running",trigger_source="manual",amazon_report_status="creating")
 assert repo.start_sync_run_if_idle(run,NOW);svc,_,transport=service(tmp_path,repository=repo);result=svc.run("seller","market",True)
 assert result.status=="creating_unconfirmed" and transport.creates==[] and transport.checks==[]

def test_failed_report_id_save_gap_does_not_recreate(tmp_path):
 class GapRepository(AdsPerformanceRepository):
  def save_created_report(self,run):return False
 repo=GapRepository(tmp_path/"ads.db");svc,_,transport=service(tmp_path,repository=repo)
 first=svc.run("seller","market",True);second=svc.run("seller","market",True)
 assert first.status==second.status=="creating_unconfirmed" and len(transport.creates)==1 and transport.checks==[]

def test_concurrent_resume_claim_allows_no_second_processing(tmp_path):
 svc,repo,transport=service(tmp_path);created=svc.run("seller","market",True)
 assert repo.claim_report_check("seller","market","profile",created.run_id,"other-claim",NOW)
 result=svc.run("seller","market",True)
 assert result.status=="already_processing" and transport.checks==[] and transport.downloads==[]

def test_status_failure_is_sanitized_and_releases_claim_for_retry(tmp_path):
 class BrokenTransport(Transport):
  def status(self,profile,report_id):raise RuntimeError("Authorization signed-secret refresh-token")
 repo=AdsPerformanceRepository(tmp_path/"ads.db");transport=BrokenTransport(repo);svc,_,_=service(tmp_path,transport,repository=repo)
 svc.run("seller","market",True);result=svc.run("seller","market",True);active=repo.active_sync_run("seller","market","profile")
 assert result.status=="unavailable" and active.report_claim is None and "signed-secret" not in str(result.public_dict()) and "refresh-token" not in str(result.public_dict())
