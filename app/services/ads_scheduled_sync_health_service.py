"""Read-only scheduled historical-sync health; never reconciles or calls Amazon."""
from datetime import timedelta
from app.amazon_ads.sync_models import AdsScheduledSyncHealth
from app.services.ads_historical_sync_execution_service import HISTORICAL_SYNC_MODE
from app.services.ads_sync_recovery_service import AdsSyncRecoveryService

def scheduled_next_due(previous,interval_hours):
    return (previous.finished_at or previous.started_at)+timedelta(hours=interval_hours) if previous else None

class AdsScheduledSyncHealthService:
    def __init__(self,config,readiness,repository,now):self.config=config;self.readiness=readiness;self.repository=repository;self.now=now
    @staticmethod
    def _safe(run):
        if not run:return None
        return {"run_id":run.sync_id,"status":run.status,"started_at":run.started_at.isoformat(),"completed_at":run.finished_at.isoformat() if run.finished_at else None,"error_code":run.error_code}
    def get(self,seller,marketplace):
        profile=str(self.readiness.settings.profile_id) if self.readiness.settings.profile_id else None;now=self.now()
        if not self.config.enabled:return AdsScheduledSyncHealth(False,"disabled",None,None,None,0,None,False,False,False,"disabled",(),False)
        ready=self.readiness.get();readiness_status="ready" if ready.manual_smoke_test_allowed else "blocked"
        runs=self.repository.list_sync_runs(seller,marketplace,profile,100,HISTORICAL_SYNC_MODE)
        scheduled=[run for run in runs if run.trigger_source=="scheduled"]
        latest=scheduled[0] if scheduled else None
        success=self.repository.latest_successful_sync(seller,marketplace,profile,HISTORICAL_SYNC_MODE,"scheduled")
        failure=self.repository.latest_failed_sync(seller,marketplace,profile,HISTORICAL_SYNC_MODE,"scheduled")
        streak=0
        for run in scheduled:
            if run.success:break
            if run.status=="failed":streak+=1
        active,stale=AdsSyncRecoveryService(self.repository,self.config.stale_run_after_hours,self.now).inspect(seller,marketplace,profile)
        next_due=scheduled_next_due(success,self.config.interval_hours);due=next_due is None or next_due<=now;overdue=bool(next_due and next_due<now and not active)
        status="stale_run" if stale else "running" if active else "readiness_blocked" if not ready.manual_smoke_test_allowed else "degraded" if streak else "due" if due else "not_due"
        warnings=("A scheduled Ads sync appears stale; trusted execution will reconcile it safely.",) if stale else (("Scheduled Ads sync has consecutive failures.",) if streak else ())
        return AdsScheduledSyncHealth(True,status,self._safe(latest),(success.finished_at or success.started_at).isoformat() if success else None,self._safe(failure),streak,next_due.isoformat() if next_due else None,overdue,bool(active),stale,readiness_status,warnings,stale or streak>=2)
