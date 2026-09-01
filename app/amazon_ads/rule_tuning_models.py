"""Immutable, safe models for offline Ads rule-tuning proposals."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib, json

ALLOWED_TUNING_PARAMETERS=("target_acos_percent","min_impressions_for_ctr","low_ctr_percent","min_clicks_for_cvr","low_cvr_percent","high_cpc_amount","wasted_spend_threshold")
PROPOSAL_STATUSES=("proposed","approved_for_future_rule_version","rejected","dismissed")

@dataclass(frozen=True)
class AdsRecommendationRuleVersion:
 rule_version_id:str; seller_id:str; marketplace_id:str; profile_id:str; version_name:str; status:str; thresholds:dict; source:str; created_by:str; notes:str|None; created_at:datetime
 def public_dict(self):return {"rule_version_id":self.rule_version_id,"version_name":self.version_name,"status":self.status,"thresholds":{k:str(v) for k,v in self.thresholds.items()},"source":self.source,"created_by":self.created_by,"notes":self.notes,"created_at":self.created_at.isoformat()}

@dataclass(frozen=True)
class AdsRuleTuningProposal:
 proposal_id:str; seller_id:str; marketplace_id:str; profile_id:str; base_rule_version_id:str; parameter_name:str; current_value:Decimal; proposed_value:Decimal; direction:str; reason_code:str; reason_summary:str; sample_size:int; confidence:str; status:str; evaluation_summary:dict; created_at:datetime; reviewed_at:datetime|None=None
 @staticmethod
 def identity(seller,market,profile,base,parameter,current,proposed,window):return hashlib.sha256(f"{seller}|{market}|{profile}|{base}|{parameter}|{current}|{proposed}|{window}".encode()).hexdigest()[:24]
 def public_dict(self):return {"proposal_id":self.proposal_id,"base_rule_version_id":self.base_rule_version_id,"parameter_name":self.parameter_name,"current_value":str(self.current_value),"proposed_value":str(self.proposed_value),"direction":self.direction,"reason_code":self.reason_code,"reason_summary":self.reason_summary,"sample_size":self.sample_size,"confidence":self.confidence,"status":self.status,"evaluation_summary":self.evaluation_summary,"created_at":self.created_at.isoformat(),"reviewed_at":self.reviewed_at.isoformat() if self.reviewed_at else None}