import pytest
from app.amazon_ads.client import AdsApiClientError,AmazonAdsClient
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.models import AdsAccessToken
class Auth:
    def get_access_token(self):return AdsAccessToken("hidden-token","Bearer",3600)
class Response:
    def __init__(self,status,payload=None):self.status_code=status;self.ok=status<400;self.payload={} if payload is None else payload
    def json(self):return self.payload
class Session:
    def __init__(self,responses):self.responses=iter(responses);self.calls=[]
    def get(self,*args,**kwargs):self.calls.append(kwargs);return next(self.responses)
    def post(self,*args,**kwargs):self.calls.append(kwargs);return next(self.responses)
def client(responses):return AmazonAdsClient(AdsSettings("id","secret","refresh","profile-1","FE"),Auth(),Session(responses))
def test_headers_scope_and_read_only_surface():
    value=client([Response(200,{})]);assert value.headers()["Amazon-Advertising-API-ClientId"]=="id" and value.headers()["Authorization"]=="Bearer hidden-token" and "Amazon-Advertising-API-Scope" not in value.headers();assert value.headers("profile-1")["Amazon-Advertising-API-Scope"]=="profile-1";assert value.get_profile_scoped("campaigns") == {};assert value._session.calls[0]["headers"]["Amazon-Advertising-API-Scope"]=="profile-1";assert value._session.calls[0]["headers"]["Accept"]=="application/json" and "Content-Type" not in value._session.calls[0]["headers"];assert not any(hasattr(value,name) for name in ("put","patch","delete"))
def test_profile_scoped_get_optional_reporting_media_type_preserves_standard_headers():
    value=client([Response(200,{})]);media_type="application/vnd.createasyncreportrequest.v3+json"
    assert value.get_profile_scoped("/reporting/reports/report",media_type=media_type)=={}
    assert value._session.calls[0]["headers"]=={"Amazon-Advertising-API-ClientId":"id","Authorization":"Bearer hidden-token","Amazon-Advertising-API-Scope":"profile-1","Accept":media_type,"Content-Type":media_type}
def test_profile_discovery_omits_scope_and_retries(monkeypatch):
    monkeypatch.setattr("app.amazon_ads.client.sleep",lambda _:None);value=client([Response(429),Response(500),Response(200,[])]);assert value.get("v2/profiles") == [] and len(value._session.calls)==3 and "Amazon-Advertising-API-Scope" not in value._session.calls[0]["headers"]
def test_non_retryable_error_is_normalized_and_redacted():
    with pytest.raises(AdsApiClientError) as error:client([Response(403)]).get("campaigns")
    assert error.value.status_code==403 and "secret" not in str(error.value).lower() and "token" not in str(error.value).lower()
def test_post_is_explicitly_read_only():
    assert client([Response(200,{"reportId":"r"})]).post_read_only("reports",json={"date":"2026-01-01"},profile_id="profile-1")=={"reportId":"r"}

@pytest.mark.parametrize("resource",("spCampaign","spAdGroup","spKeyword","spTargetingClause"))
def test_v3_list_media_type_preserves_standard_ads_headers(resource):
    value=client([Response(200,{})]);media_type=f"application/vnd.{resource}.v3+json"
    value.post_read_only("/sp/campaigns/list",json={"maxResults":10},profile_id="profile-1",media_type=media_type)
    request=value._session.calls[0]
    assert request["json"]=={"maxResults":10}
    assert request["headers"]=={"Amazon-Advertising-API-ClientId":"id","Authorization":"Bearer hidden-token","Amazon-Advertising-API-Scope":"profile-1","Accept":media_type,"Content-Type":media_type}

def test_advertiser_query_uses_unified_headers_only_for_that_path():
    session=Session([Response(200,{"advertiserAccounts":[]}),Response(200,{}),Response(200,[])])
    urls=[]
    original_post=session.post
    def post(url,**kwargs):urls.append(url);return original_post(url,**kwargs)
    session.post=post
    value=AmazonAdsClient(AdsSettings("id","secret","refresh","profile-1","EU"),Auth(),session)
    assert value.post_read_only("/adsApi/v1/query/advertiserAccounts",json={},profile_id="profile-1")=={"advertiserAccounts":[]}
    assert urls[0]=="https://advertising-api-eu.amazon.com/adsApi/v1/query/advertiserAccounts"
    unified=session.calls[0]
    assert unified["json"]=={} and unified["headers"]=={"Amazon-Ads-ClientId":"id","Authorization":"Bearer hidden-token","Accept":"application/json","Content-Type":"application/json"}
    assert value.post_read_only("/reporting/reports",json={},profile_id="profile-1")=={}
    assert value.get("/v2/profiles")==[]
    for standard in session.calls[1:]:
        assert standard["headers"]["Amazon-Advertising-API-ClientId"]=="id"
        assert "Amazon-Ads-ClientId" not in standard["headers"]
    assert session.calls[1]["headers"]["Amazon-Advertising-API-Scope"]=="profile-1"
    assert "Amazon-Advertising-API-Scope" not in session.calls[2]["headers"]
