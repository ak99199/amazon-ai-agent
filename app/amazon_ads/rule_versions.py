"""Baseline rule-version creation; proposed versions are never active here."""
from datetime import datetime, timezone
from app.amazon_ads.rule_tuning_models import AdsRecommendationRuleVersion
from app.services.ads_signal_service import AdsRecommendationThresholds

class AdsRuleVersions:
 @staticmethod
 def baseline(seller_id,marketplace_id,profile_id,thresholds=None,now=None):
  value=thresholds or AdsRecommendationThresholds.from_environment(); timestamp=(now or (lambda:datetime.now(timezone.utc)))()
  fields={name:getattr(value,name) for name in ("target_acos_percent","min_impressions_for_ctr","low_ctr_percent","min_clicks_for_cvr","low_cvr_percent","high_cpc_amount","wasted_spend_threshold")}
  return AdsRecommendationRuleVersion("baseline",seller_id,marketplace_id,str(profile_id),"Baseline deterministic rules","active",fields,"baseline","system",None,timestamp)