"""Normalized, decimal-safe Amazon Ads reporting models."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib,json
@dataclass(frozen=True)
class AdsPerformanceDaily:
    seller_id:str; marketplace_id:str; profile_id:str; date:date; ad_product:str; campaign_id:str|None=None; campaign_name:str|None=None; ad_group_id:str|None=None; ad_group_name:str|None=None; keyword_id:str|None=None; keyword_text:str|None=None; match_type:str|None=None; target_id:str|None=None; target_expression:str|None=None; search_term:str|None=None; currency:str|None=None; impressions:int=0; clicks:int=0; spend:Decimal=Decimal("0"); orders:int=0; units:int=0; sales:Decimal=Decimal("0")
    @property
    def dimension_key(self):
        dimensions={"campaign_id":self.campaign_id,"ad_group_id":self.ad_group_id,"keyword_id":self.keyword_id,"target_id":self.target_id,"search_term":self.search_term}
        return hashlib.sha256(json.dumps(dimensions,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
@dataclass(frozen=True)
class AdsReportRequest:
    ad_product:str; report_level:str; start_date:date; end_date:date; columns:tuple[str,...]; group_by:tuple[str,...]