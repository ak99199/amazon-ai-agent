import pytest
from app.amazon_ads.profiles import AdsProfileAmbiguityError,AdsProfilesService
class Client:
    def __init__(self,payload):self.payload=payload;self.calls=[]
    def get(self,path,profile_id=None):self.calls.append((path,profile_id));return self.payload
def test_multiple_profiles_normalize_and_discovery_has_no_scope():
    client=Client([{"profileId":1,"countryCode":"IN","currencyCode":"INR","timezone":"Asia/Kolkata","accountInfo":{"id":"acct","type":"seller"}},{"profileId":"2","countryCode":"US","accountId":"us"}]);profiles=AdsProfilesService(client).list_profiles()
    assert [profile.profile_id for profile in profiles]==["1","2"] and profiles[0].account_id=="acct" and client.calls==[("/v2/profiles",None)]
def test_india_profile_selection_and_ambiguity():
    assert AdsProfilesService(Client([{"profileId":"in","countryCode":"IN"}])).find_india_profile().profile_id=="in"
    with pytest.raises(AdsProfileAmbiguityError):AdsProfilesService(Client([{"profileId":"a","countryCode":"IN"},{"profileId":"b","countryCode":"IN"}])).find_india_profile()