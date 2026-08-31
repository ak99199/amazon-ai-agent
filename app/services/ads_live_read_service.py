"""Gate optional live Ads reads before any adapter or network call occurs."""
from os import getenv
from app.amazon_ads.live_models import AdsLiveProfile, LiveReadStatus
from app.amazon_ads.live_read import AdsLiveReadConfig

class AdsLiveReadBlockedError(RuntimeError): pass
class AdsLiveReadService:
    def __init__(self,settings,profiles_service=None,read_adapter=None,config=None,approval_status=None):
        self.settings=settings; self.profiles_service=profiles_service; self.read_adapter=read_adapter
        self.config=config or AdsLiveReadConfig.from_environment(); self.approval_status=approval_status
    def status(self):
        approval=(self.approval_status or getenv("AMAZON_ADS_APPROVAL_STATUS","pending")).lower()
        complete=not self.settings.missing_auth_fields; profile=bool(self.settings.profile_id)
        if self.config.use_mock_data:return LiveReadStatus("mock",self.config.live_read_enabled,True,approval,complete,profile,False)
        if not self.config.live_read_enabled:return LiveReadStatus("disabled",False,False,approval,complete,profile,False)
        if approval!="approved":return LiveReadStatus("blocked_approval",True,False,approval,complete,profile,False,"approval_pending")
        if not complete:return LiveReadStatus("blocked_config",True,False,approval,False,profile,False,"configuration_incomplete")
        if not profile:return LiveReadStatus("blocked_profile",True,False,approval,True,False,False,"profile_not_selected")
        return LiveReadStatus("ready_live",True,False,approval,True,True,True)
    def _ready(self):
        state=self.status()
        if not state.ready:raise AdsLiveReadBlockedError(state.mode)
    def discover_profiles(self):
        self._ready()
        profiles=[]
        for profile in self.profiles_service.list_profiles():
            profiles.append(AdsLiveProfile(str(profile.profile_id),profile.country_code,profile.currency_code,getattr(profile,"timezone",None),getattr(profile,"account_type",None),getattr(profile,"account_name",None) or (profile.account_info.get("name") if isinstance(getattr(profile,"account_info",None),dict) and isinstance(profile.account_info.get("name"),str) else None)))
        return profiles
    def read_entities(self):
        self._ready(); profile_id=self.settings.profile_id
        return {"campaigns":self.read_adapter.campaigns(profile_id),"ad_groups":self.read_adapter.ad_groups(profile_id),"keywords":self.read_adapter.keywords(profile_id),"targets":self.read_adapter.targets(profile_id)}