"""Normalized, secret-free Ads manual-sync gate and run models."""
from dataclasses import asdict, dataclass
from datetime import date, datetime

@dataclass(frozen=True)
class AdsSyncGateResult:
    allowed: bool; mode: str | None; status_code: str; status_message: str
    approval_status: str; live_read_enabled: bool; mock_data_enabled: bool; config_complete: bool; profile_selected: bool
    sync_in_progress: bool; cooldown_active: bool; requested_start_date: date; requested_end_date: date; window_days: int; checks: tuple[dict[str,object],...]
    def public_dict(self):
        result=asdict(self);result["requested_start_date"]=self.requested_start_date.isoformat();result["requested_end_date"]=self.requested_end_date.isoformat();return result

@dataclass(frozen=True)
class AdsManualSyncResult:
    sync_id: str; mode: str; seller_id: str; marketplace_id: str; profile_id: str | None; start_date: date; end_date: date; started_at: datetime; finished_at: datetime | None; success: bool; status: str
    campaigns_fetched:int=0;ad_groups_fetched:int=0;keywords_fetched:int=0;targets_fetched:int=0;report_rows_received:int=0;rows_normalized:int=0;rows_saved:int=0;rows_failed:int=0;error_code:str|None=None;safe_error_message:str|None=None
    def public_dict(self):
        result=asdict(self)
        for field in ("start_date","end_date","started_at","finished_at"):
            if result[field] is not None:result[field]=result[field].isoformat()
        return result

@dataclass(frozen=True)
class AdsManualHistoricalSyncResult:
    status:str;run_id:str|None;started_at:datetime|None;completed_at:datetime|None;rows_persisted:int;valid_empty:bool;message:str;error_code:str|None=None
    def public_dict(self):
        result=asdict(self)
        for field in ("started_at","completed_at"):
            if result[field] is not None:result[field]=result[field].isoformat()
        return result
