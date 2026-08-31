"""Deterministic local gate for manual, read-only Ads synchronization."""
from datetime import date, datetime, timedelta, timezone
from os import getenv
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.sync_models import AdsSyncGateResult

class AdsSyncGateService:
    def __init__(self,settings,repository,live_config=None,approval_status=None,now=None,cooldown_seconds=None):
        self.settings=settings;self.repository=repository;self.live_config=live_config or AdsLiveReadConfig.from_environment();self.approval_status=approval_status;self.now=now or (lambda:datetime.now(timezone.utc));self.cooldown_seconds=int(cooldown_seconds if cooldown_seconds is not None else getenv("AMAZON_ADS_MANUAL_SYNC_COOLDOWN_SECONDS","60"))
    def evaluate(self,seller_id,marketplace_id,profile_id=None,start_date=None,end_date=None,window_days=7):
        today=self.now().date();profile_id=profile_id or self.settings.profile_id
        start_date,end_date=self._dates(start_date,end_date,window_days,today)
        approval=(self.approval_status or getenv("AMAZON_ADS_APPROVAL_STATUS","pending")).lower();config=not self.settings.missing_auth_fields;selected=bool(profile_id)
        active=self.repository.has_active_sync(seller_id,marketplace_id,profile_id,self.now()-timedelta(minutes=30)) if profile_id else False
        recent=self.repository.latest_sync_run(seller_id,marketplace_id,profile_id) if profile_id else None
        cooldown=bool(recent and recent["started_at"] and datetime.fromisoformat(recent["started_at"]) > self.now()-timedelta(seconds=max(0,self.cooldown_seconds)))
        checks=[]; add=lambda name,passed,reason:checks.append({"name":name,"passed":passed,"reason":reason})
        if self.live_config.use_mock_data: mode="mock";add("MOCK_MODE",True,"Injected mock/local data mode is enabled.")
        elif not self.live_config.live_read_enabled: mode=None;add("FEATURE_FLAG",False,"Live read is disabled and mock mode is off.")
        else: mode="live";add("FEATURE_FLAG",True,"Live read is explicitly enabled.")
        add("APPROVAL",approval=="approved" if mode=="live" else True,"Approval is ready." if approval=="approved" or mode=="mock" else "Amazon Ads approval is not ready.")
        add("CONFIG",config if mode=="live" else True,"Configuration is complete." if config or mode=="mock" else "Ads configuration is incomplete.")
        add("PROFILE",selected if mode=="live" else True,"Profile is selected." if selected or mode=="mock" else "Ads profile is not selected.")
        add("DATE_RANGE",start_date<=end_date and end_date<=today and (end_date-start_date).days<=89,"Requested date range is bounded.")
        add("CONCURRENCY",not active,"No active sync is running." if not active else "A sync is already running.")
        add("COOLDOWN",not cooldown,"Cooldown is clear." if not cooldown else "Manual sync cooldown is active.")
        failed=next((item for item in checks if not item["passed"]),None)
        code="allowed_"+mode if not failed and mode else self._code(failed["name"] if failed else "MODE",start_date,end_date,today)
        return AdsSyncGateResult(not bool(failed) and bool(mode),mode,code,"Manual sync is allowed." if not failed and mode else failed["reason"] if failed else "No sync mode is enabled.",approval,self.live_config.live_read_enabled,self.live_config.use_mock_data,config,selected,active,cooldown,start_date,end_date,(end_date-start_date).days+1,tuple(checks))
    @staticmethod
    def _dates(start,end,window,today):
        if start is None and end is None:
            window=int(window);return today-timedelta(days=window-1),today
        if not isinstance(start,date) or not isinstance(end,date):raise ValueError("Sync dates are invalid")
        return start,end
    @staticmethod
    def _code(name,start,end,today):
        if start>end:return "blocked_date_range"
        if end>today:return "blocked_future_date"
        if (end-start).days>89:return "blocked_window_too_large"
        return {"APPROVAL":"blocked_approval","CONFIG":"blocked_config","PROFILE":"blocked_profile","FEATURE_FLAG":"blocked_live_disabled","MOCK_MODE":"blocked_no_mode","CONCURRENCY":"blocked_in_progress","COOLDOWN":"blocked_cooldown"}.get(name,"error")
