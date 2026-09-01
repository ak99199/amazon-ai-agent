"""Safe, network-free production readiness for Amazon Ads live reads."""
from os import getenv
from app.amazon_ads.config import ADS_REGION_ENDPOINTS,AdsSettings
from app.amazon_ads.live_models import AdsProductionReadiness
from app.amazon_ads.live_read import AdsLiveReadConfig

class AdsProductionReadinessService:
 def __init__(self,settings=None,config=None,approval_status=None):self.settings=settings or AdsSettings.from_environment();self.config=config or AdsLiveReadConfig.from_environment();self.approval_status=approval_status
 def get(self):
  approval=(self.approval_status or getenv("AMAZON_ADS_APPROVAL_STATUS","pending")).lower();approval=approval if approval in ("pending","approved","rejected","unknown") else "unknown"
  settings=self.settings;has_id=bool(settings.client_id);has_secret=bool(settings.client_secret);has_refresh=bool(settings.refresh_token);complete=has_id and has_secret and has_refresh;profile=bool(settings.profile_id);region=settings.region.upper();region_valid=region in ADS_REGION_ENDPOINTS;approved=approval=="approved";live=bool(self.config.live_read_enabled);mock=bool(self.config.use_mock_data)
  reasons=[]
  if not approved:reasons.append("approval_not_granted")
  if not complete:reasons.append("credential_configuration_incomplete")
  if not profile:reasons.append("profile_not_selected")
  if not region_valid:reasons.append("region_invalid")
  if not live:reasons.append("live_read_disabled")
  if mock:reasons.append("mock_mode_enabled")
  ready=not reasons;warnings=("Amazon Ads API approval is still pending. Live requests remain blocked.",) if approval=="pending" else ()
  return AdsProductionReadiness(approval,live,mock,region,profile,has_id,has_secret,has_refresh,complete,profile,region_valid,approved,ready,ready,tuple(reasons),warnings)
