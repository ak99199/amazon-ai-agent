"""Normalized safe models for the optional Amazon Ads live-read boundary."""
from dataclasses import asdict, dataclass
from decimal import Decimal
from datetime import datetime

@dataclass(frozen=True)
class LiveReadStatus:
    mode: str
    live_read_enabled: bool
    mock_data_enabled: bool
    approval_status: str
    config_complete: bool
    profile_selected: bool
    ready: bool
    last_error_code: str | None = None
    def public_dict(self): return asdict(self)

@dataclass(frozen=True)
class AdsLiveProfile:
    profile_id: str; country_code: str | None = None; currency_code: str | None = None; timezone: str | None = None; account_type: str | None = None; account_name: str | None = None
    def public_dict(self): return asdict(self)

@dataclass(frozen=True)
class AdsLiveAdGroup:
    ad_group_id: str; campaign_id: str; name: str | None = None; state: str | None = None; default_bid: Decimal | None = None
    def public_dict(self):
        result=asdict(self); result["default_bid"]=str(self.default_bid) if self.default_bid is not None else None; return result

@dataclass(frozen=True)
class AdsLiveTarget:
    target_id: str; campaign_id: str | None = None; ad_group_id: str | None = None; expression: str | None = None; resolved_expression: str | None = None; state: str | None = None; bid: Decimal | None = None
    def public_dict(self):
        result=asdict(self); result["bid"]=str(self.bid) if self.bid is not None else None; return result

@dataclass(frozen=True)
class AdsLiveReportStatus:
    report_id: str; status: str; location: str | None = None

@dataclass(frozen=True)
class AdsProductionReadiness:
    approval_status:str;live_read_enabled:bool;mock_mode:bool;region:str;profile_id_present:bool;has_client_id:bool;has_client_secret:bool;has_refresh_token:bool;credential_configuration_complete:bool;profile_selected:bool;region_valid:bool;approval_granted:bool;live_read_ready:bool;manual_smoke_test_allowed:bool;blocking_reasons:tuple[str,...];warnings:tuple[str,...]
    def public_dict(self):return asdict(self)

@dataclass(frozen=True)
class AdsLiveSmokeTestResult:
    status:str;started_at:datetime;completed_at:datetime;region:str;profile_id_present:bool;request_stage:str;http_status:int|None;campaign_read_success:bool;records_observed:int;message:str
    def public_dict(self):
        value=asdict(self);value["started_at"]=self.started_at.isoformat();value["completed_at"]=self.completed_at.isoformat();return value
