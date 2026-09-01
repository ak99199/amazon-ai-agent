"""Read-only, seller-scoped resolution of recommendation rule thresholds."""
from dataclasses import dataclass
from app.amazon_ads.rule_tuning_models import ALLOWED_TUNING_PARAMETERS,validate_threshold_snapshot
from app.services.ads_signal_service import AdsRecommendationConfigurationError,AdsRecommendationThresholds

class AdsRuleVersionConfigurationError(AdsRecommendationConfigurationError):pass

@dataclass(frozen=True)
class ResolvedAdsRuleVersion:
 thresholds:AdsRecommendationThresholds;rule_version_id:str|None;rule_version_name:str|None;source:str;is_persisted:bool;fallback_used:bool

class AdsRuleVersionResolver:
 def __init__(self,repository):self.repository=repository
 def resolve(self,seller_id,marketplace_id,profile_id):
  try:row=self.repository.get_active_rule_version(seller_id,marketplace_id,str(profile_id))
  except Exception as error:raise AdsRuleVersionConfigurationError("Active Ads rule configuration is unavailable") from error
  if row is None:return ResolvedAdsRuleVersion(AdsRecommendationThresholds.from_environment(),None,None,"environment",False,True)
  if row.get("status")!="active" or row.get("seller_id")!=seller_id or row.get("marketplace_id")!=marketplace_id or str(row.get("profile_id"))!=str(profile_id):raise AdsRuleVersionConfigurationError("Active Ads rule version scope or status is invalid")
  parsed,well,white,bounds=validate_threshold_snapshot(row.get("thresholds"))
  if not (well and white and bounds) or set(parsed)!=set(ALLOWED_TUNING_PARAMETERS):raise AdsRuleVersionConfigurationError("Active Ads rule threshold snapshot is invalid")
  try:
   values=dict(parsed);values["min_impressions_for_ctr"]=int(values["min_impressions_for_ctr"]);values["min_clicks_for_cvr"]=int(values["min_clicks_for_cvr"]);thresholds=AdsRecommendationThresholds(**values)
  except (TypeError,ValueError,ArithmeticError) as error:raise AdsRuleVersionConfigurationError("Active Ads rule threshold snapshot cannot be converted") from error
  return ResolvedAdsRuleVersion(thresholds,row["rule_version_id"],row.get("version_name"),row.get("source") or "persisted",True,False)
 def resolve_thresholds(self,seller,marketplace,profile):return self.resolve(seller,marketplace,profile).thresholds
