"""Immutable, safe models for offline Ads rule-tuning proposals."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib, json

ALLOWED_TUNING_PARAMETERS=("target_acos_percent","min_impressions_for_ctr","low_ctr_percent","min_clicks_for_cvr","low_cvr_percent","high_cpc_amount","wasted_spend_threshold")
PROPOSAL_STATUSES=("proposed","approved_for_future_rule_version","rejected","dismissed")
MAX_RELATIVE_TUNING_CHANGE=Decimal("25")
TUNING_PARAMETER_BOUNDS={"target_acos_percent":(Decimal("5"),Decimal("100")),"min_impressions_for_ctr":(Decimal("1"),None),"low_ctr_percent":(Decimal("0"),Decimal("100")),"min_clicks_for_cvr":(Decimal("1"),None),"low_cvr_percent":(Decimal("0"),Decimal("100")),"high_cpc_amount":(Decimal("0.01"),None),"wasted_spend_threshold":(Decimal("0.01"),None)}
def relative_change_percent(current,proposed):
 current=Decimal(str(current));proposed=Decimal(str(proposed))
 if current==0:return Decimal("0") if proposed==0 else Decimal("Infinity")
 return abs(proposed-current)/abs(current)*Decimal("100")
def validate_threshold_snapshot(values):
 parsed={};well_formed=isinstance(values,dict) and bool(values)
 if well_formed:
  try:
   for name,value in values.items():
    number=Decimal(str(value))
    if not number.is_finite() or (name in ("min_impressions_for_ctr","min_clicks_for_cvr") and number!=number.to_integral_value()):raise ValueError
    parsed[name]=number
  except (ArithmeticError,ValueError,TypeError):well_formed=False
 whitelisted=well_formed and set(parsed)==set(ALLOWED_TUNING_PARAMETERS)
 bounds_valid=whitelisted and all(TUNING_PARAMETER_BOUNDS[name][0]<=value and (TUNING_PARAMETER_BOUNDS[name][1] is None or value<=TUNING_PARAMETER_BOUNDS[name][1]) for name,value in parsed.items())
 return parsed,well_formed,whitelisted,bounds_valid

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
