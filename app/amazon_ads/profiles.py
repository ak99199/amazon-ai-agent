"""Read-only Amazon Ads profile discovery."""
from app.amazon_ads.models import AdsProfile
class AdsProfileAmbiguityError(Exception):pass
class AdsProfilesService:
    def __init__(self,client):self._client=client
    def list_profiles(self):
        payload=self._client.get("/v2/profiles",profile_id=None)
        if not isinstance(payload,list):return []
        profiles=[]
        for item in payload:
            if isinstance(item,dict):
                try:profiles.append(AdsProfile.from_api(item))
                except ValueError:continue
        return profiles
    @staticmethod
    def india_profiles(profiles):return [profile for profile in profiles if profile.country_code=="IN"]
    def find_india_profile(self):
        candidates=self.india_profiles(self.list_profiles())
        if len(candidates)>1:raise AdsProfileAmbiguityError("Multiple India Amazon Ads profiles require explicit selection")
        return candidates[0] if candidates else None