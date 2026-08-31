"""Deterministic approval/configuration/data readiness for the Ads subsystem."""
from os import getenv
from dataclasses import asdict,dataclass
from app.amazon_ads.config import AdsSettings
@dataclass(frozen=True)
class AdsReadinessResult:
    approval_status:str;config_status:str;profile_status:str;data_status:str;overall_status:str;has_client_id:bool;has_client_secret:bool;has_refresh_token:bool;has_profile_id:bool;has_historical_data:bool;performance_row_count:int;ingestion_run_count:int;last_ingestion_at:str|None;last_successful_ingestion_at:str|None;approval_message:str;config_message:str;profile_message:str;data_message:str;live_read_enabled:bool=False;mock_data_enabled:bool=True;live_read_status:str="disabled"
    def public_dict(self):return asdict(self)
class AdsReadinessService:
    def __init__(self,diagnostics,settings=None,approval_status=None):self._diagnostics=diagnostics;self._settings=settings or AdsSettings.from_environment();self._approval=approval_status
    def get(self,seller_id,marketplace_id):
        approval=(self._approval or getenv("AMAZON_ADS_APPROVAL_STATUS","pending")).lower();approval=approval if approval in ("pending","approved","rejected","unknown") else "unknown";settings=self._settings;has_id=bool(settings.client_id);has_secret=bool(settings.client_secret);has_refresh=bool(settings.refresh_token);has_profile=bool(settings.profile_id)
        diagnostics=self._diagnostics.get(seller_id,marketplace_id,settings.profile_id) if has_profile else self._diagnostics.get(seller_id,marketplace_id,None);has_data=diagnostics["performance_row_count"]>0
        overall="approval_pending" if approval!="approved" else "configuration_incomplete" if not (has_id and has_secret and has_refresh) else "profile_not_selected" if not has_profile else "no_ads_data" if not has_data else "ready"
        try:
            from app.amazon_ads.live_read import AdsLiveReadConfig
            live=AdsLiveReadConfig.from_environment()
            live_status="mock" if live.use_mock_data else "blocked_approval" if live.live_read_enabled and approval!="approved" else "blocked_config" if live.live_read_enabled and not (has_id and has_secret and has_refresh) else "blocked_profile" if live.live_read_enabled and not has_profile else "ready_live" if live.live_read_enabled else "disabled"
        except Exception:
            live=type("LiveConfig",(),{"live_read_enabled":False,"use_mock_data":True})(); live_status="configuration_error"
        return AdsReadinessResult(approval,"complete" if has_id and has_secret and has_refresh else "incomplete","selected" if has_profile else "not_selected","available" if has_data else "no_data",overall,has_id,has_secret,has_refresh,has_profile,has_data,diagnostics["performance_row_count"],diagnostics["ingestion_run_count"],diagnostics["last_ingestion_at"],diagnostics["last_successful_ingestion_at"],f"Amazon Ads approval is {approval}.","Ads credentials are complete." if has_id and has_secret and has_refresh else "Ads credentials are incomplete.","Ads profile is selected." if has_profile else "Ads profile is not selected.","Historical Ads data is available." if has_data else "No historical Ads data is available.",live.live_read_enabled,live.use_mock_data,live_status)