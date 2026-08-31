"""Read-only Ads ingestion domain models."""
from dataclasses import dataclass
from datetime import datetime,date
from decimal import Decimal
@dataclass(frozen=True)
class AdsCampaign:
    profile_id:str;campaign_id:str;campaign_name:str|None=None;state:str|None=None;daily_budget:Decimal|None=None;budget_type:str|None=None;targeting_type:str|None=None;start_date:date|None=None;end_date:date|None=None;portfolio_id:str|None=None
@dataclass(frozen=True)
class AdsKeyword:
    profile_id:str;campaign_id:str|None=None;ad_group_id:str|None=None;keyword_id:str|None=None;keyword_text:str|None=None;match_type:str|None=None;state:str|None=None;bid:Decimal|None=None;target_id:str|None=None;target_expression:str|None=None
@dataclass(frozen=True)
class AdsIngestionResult:
    run_id:str;started_at:datetime;finished_at:datetime;campaigns_fetched:int;keywords_fetched:int;targets_fetched:int;report_rows_received:int;rows_normalized:int;rows_saved:int;rows_failed:int;success:bool;errors:tuple[str,...]