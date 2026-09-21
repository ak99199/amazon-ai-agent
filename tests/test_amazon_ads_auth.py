import pytest
from app.amazon_ads.auth import AdsAuthenticationError,AdsLwaAuthenticator,LWA_TOKEN_ENDPOINT
from app.amazon_ads.config import AdsSettings
class Response:
    def __init__(self,status,payload=None):self.status_code=status;self.ok=status<400;self.payload=payload or {}
    def json(self):return self.payload
class Session:
    def __init__(self,response):self.response=response;self.url=None;self.data=None
    def post(self,url,**kwargs):self.url=url;self.data=kwargs["data"];return self.response
def settings():return AdsSettings("ads-id","ads-secret","ads-refresh",None,"FE")
def test_lwa_refresh_flow_is_normalized():
    session=Session(Response(200,{"access_token":"short-lived","token_type":"bearer","expires_in":3600}));token=AdsLwaAuthenticator(settings(),session).get_access_token()
    assert session.url==LWA_TOKEN_ENDPOINT and session.data=={"grant_type":"refresh_token","refresh_token":"ads-refresh","client_id":"ads-id","client_secret":"ads-secret"} and token.expires_in==3600 and token.access_token=="short-lived"
def test_authentication_error_redacts_credentials():
    with pytest.raises(AdsAuthenticationError) as error:AdsLwaAuthenticator(settings(),Session(Response(401))).get_access_token()
    assert "ads-secret" not in str(error.value) and "ads-refresh" not in str(error.value)
def test_authorization_code_exchange_uses_lwa_and_returns_refresh_token():
    session=Session(Response(200,{"access_token":"access-value","refresh_token":"refresh-value"}))
    token=AdsLwaAuthenticator(settings(),session).exchange_authorization_code("code-value","https://example.com/")
    assert session.url==LWA_TOKEN_ENDPOINT and session.data=={"grant_type":"authorization_code","code":"code-value","client_id":"ads-id","client_secret":"ads-secret","redirect_uri":"https://example.com/"}
    assert token=="refresh-value"
    with pytest.raises(AdsAuthenticationError):AdsLwaAuthenticator(settings(),Session(Response(200,{"access_token":"only-access"}))).exchange_authorization_code("code-value","https://example.com/")
