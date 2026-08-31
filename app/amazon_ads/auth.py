"""Login with Amazon refresh-token authentication for Amazon Ads only."""
import requests
from app.amazon_ads.config import AdsConfigurationError
from app.amazon_ads.models import AdsAccessToken
LWA_TOKEN_ENDPOINT="https://api.amazon.com/auth/o2/token"
class AdsAuthenticationError(Exception):pass
class AdsLwaAuthenticator:
    def __init__(self,settings,session=None,timeout=30):self._settings=settings;self._session=session or requests.Session();self._timeout=timeout
    def get_access_token(self):
        try:settings=self._settings.require_auth()
        except AdsConfigurationError as error:raise AdsAuthenticationError("Amazon Ads authentication is not configured") from error
        try:response=self._session.post(LWA_TOKEN_ENDPOINT,data={"grant_type":"refresh_token","refresh_token":settings.refresh_token,"client_id":settings.client_id,"client_secret":settings.client_secret},timeout=self._timeout)
        except requests.Timeout as error:raise AdsAuthenticationError("Amazon Ads authentication timed out") from error
        except requests.RequestException as error:raise AdsAuthenticationError("Amazon Ads authentication request failed") from error
        if not response.ok:raise AdsAuthenticationError("Amazon Ads authentication was rejected")
        try:payload=response.json()
        except ValueError as error:raise AdsAuthenticationError("Amazon Ads authentication returned invalid JSON") from error
        token=payload.get("access_token") if isinstance(payload,dict) else None;token_type=payload.get("token_type", "Bearer") if isinstance(payload,dict) else "Bearer";expires=payload.get("expires_in") if isinstance(payload,dict) else None
        if not isinstance(token,str) or not token or not isinstance(expires,int):raise AdsAuthenticationError("Amazon Ads authentication returned an invalid response")
        return AdsAccessToken(token,token_type if isinstance(token_type,str) else "Bearer",expires)