"""Offline, bounded rule-threshold evaluation only; never activates a rule."""
from decimal import Decimal
from app.amazon_ads.rule_tuning_models import ALLOWED_TUNING_PARAMETERS, AdsRuleTuningProposal
from app.amazon_ads.rule_versions import AdsRuleVersions

class AdsRuleEvaluationService:
 def __init__(self,effectiveness_service,min_sample=20,max_relative_change=Decimal("25")):
  self.effectiveness_service=effectiveness_service;self.min_sample=int(min_sample);self.max_relative_change=Decimal(str(max_relative_change))
 def evaluate(self,seller_id,marketplace_id,profile_id,window=90):
  summary=self.effectiveness_service.get(seller_id,marketplace_id,profile_id,window);baseline=AdsRuleVersions.baseline(seller_id,marketplace_id,profile_id);reviewed=summary.total_reviewed
  if reviewed<self.min_sample:return baseline,[],{"reason_code":"INSUFFICIENT_DATA","simulation_eligible_count":0,"simulation_excluded_count":reviewed}
  proposals=[]
  for item in summary.by_code:
   if item["reviewed"]<self.min_sample or item["rejection_rate"] is None:continue
   parameter="target_acos_percent" if item["recommendation_code"]=="HIGH_ACOS" else "wasted_spend_threshold" if item["recommendation_code"]=="WASTED_SPEND" else None
   if not parameter or item["rejection_rate"]<Decimal("70"):continue
   current=Decimal(str(baseline.thresholds[parameter]));proposed=self._bounded(current,Decimal("10"),parameter)
   if proposed==current:continue
   direction="increase";effect={"baseline_recommendation_count":reviewed,"candidate_recommendation_count":reviewed,"estimated_recommendations_added":0,"estimated_recommendations_removed":0,"estimated_approvals_retained":item["approved"],"estimated_rejected_recommendations_avoided":item["rejected"],"simulation_eligible_count":item["reviewed"],"simulation_excluded_count":reviewed-item["reviewed"]}
   proposal_id=AdsRuleTuningProposal.identity(seller_id,marketplace_id,str(profile_id),baseline.rule_version_id,parameter,current,proposed,window)
   proposals.append(AdsRuleTuningProposal(proposal_id,seller_id,marketplace_id,str(profile_id),baseline.rule_version_id,parameter,current,proposed,direction,"HIGH_REJECTION_RATE","Offline human-disagreement proxy; no rule is changed.",item["reviewed"],"medium" if item["reviewed"]>=40 else "low","proposed",effect,baseline.created_at))
  return baseline,proposals,{"reason_code":"BALANCED_IMPROVEMENT","simulation_eligible_count":reviewed,"simulation_excluded_count":0}
 def _bounded(self,current,percent,parameter):
  value=current*(Decimal("1")+min(percent,self.max_relative_change)/Decimal("100"));minimum=Decimal("5") if parameter=="target_acos_percent" else Decimal("0.01");maximum=Decimal("100") if parameter=="target_acos_percent" else None
  return min(value,maximum) if maximum is not None else max(value,minimum)