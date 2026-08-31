"""Manual-only, gated, read-side Ads synchronization."""
from datetime import datetime, timezone
from uuid import uuid4
from app.amazon_ads.sync_models import AdsManualSyncResult

class AdsManualSyncService:
    def __init__(self,gate_service,repository,runner=None,now=None):self.gate_service=gate_service;self.repository=repository;self.runner=runner;self.now=now or (lambda:datetime.now(timezone.utc))
    def status(self,seller_id,marketplace_id,profile_id=None):
        gate=self.gate_service.evaluate(seller_id,marketplace_id,profile_id);latest=self.repository.latest_sync_run(seller_id,marketplace_id,profile_id or self.gate_service.settings.profile_id)
        return {"gate":gate.public_dict(),"latest_sync":self._public_row(latest)}
    def run(self,seller_id,marketplace_id,profile_id=None,start_date=None,end_date=None,window_days=7):
        gate=self.gate_service.evaluate(seller_id,marketplace_id,profile_id,start_date,end_date,window_days)
        profile_id=profile_id or self.gate_service.settings.profile_id
        if not gate.allowed:return gate
        started=self.now(); sync_id=str(uuid4()); starting=AdsManualSyncResult(sync_id,gate.mode,seller_id,marketplace_id,profile_id,gate.requested_start_date,gate.requested_end_date,started,None,False,"starting")
        self.repository.save_sync_run(starting)
        try:
            result=self.runner(gate.mode,seller_id,marketplace_id,profile_id,gate.requested_start_date,gate.requested_end_date) if self.runner else {}
            if not isinstance(result,dict):raise ValueError("sync runner result is invalid")
            finished=self.now(); completed=AdsManualSyncResult(sync_id,gate.mode,seller_id,marketplace_id,profile_id,gate.requested_start_date,gate.requested_end_date,started,finished,True,"completed",result.get("campaigns_fetched",0),result.get("ad_groups_fetched",0),result.get("keywords_fetched",0),result.get("targets_fetched",0),result.get("report_rows_received",0),result.get("rows_normalized",0),result.get("rows_saved",0),result.get("rows_failed",0))
        except Exception:
            completed=AdsManualSyncResult(sync_id,gate.mode,seller_id,marketplace_id,profile_id,gate.requested_start_date,gate.requested_end_date,started,self.now(),False,"failed",error_code="unknown_error",safe_error_message="Ads sync did not complete.")
        return self.repository.save_sync_run(completed)
    @staticmethod
    def _public_row(row):
        if not row:return None
        fields=("sync_id","mode","start_date","end_date","started_at","finished_at","status","success","rows_saved","error_code")
        return {field:row[field] for field in fields}
