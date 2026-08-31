"""Read-only Amazon Ads API client; no campaign mutation methods are exposed."""
from time import sleep
import requests
from app.amazon_ads.models import AdsApiErrorResponse
class AdsApiClientError(Exception):
    def __init__(self,status_code,message,retryable=False):super().__init__(message);self.status_code=status_code;self.retryable=retryable
    def public_error(self):return AdsApiErrorResponse(self.status_code,str(self),self.retryable)
class AmazonAdsClient:
    def __init__(self,settings,authenticator,session=None,max_attempts=3,timeout=30):self._settings=settings;self._authenticator=authenticator;self._session=session or requests.Session();self._max_attempts=max(1,max_attempts);self._timeout=timeout
    def headers(self,profile_id=None):
        token=self._authenticator.get_access_token();headers={"Amazon-Advertising-API-ClientId":self._settings.require_auth().client_id,"Authorization":f"Bearer {token.access_token}","Accept":"application/json"}
        if profile_id:headers["Amazon-Advertising-API-Scope"]=str(profile_id)
        return headers
    def get(self,path,params=None,profile_id=None):return self._request("get",path,params=params,profile_id=profile_id)
    def get_profile_scoped(self,path,params=None,profile_id=None):
        profile_id=profile_id or self._settings.require_profile_api().profile_id;return self.get(path,params,profile_id)
    def post_read_only(self,path,json=None,params=None,profile_id=None):
        """For read/report creation operations only; campaign mutation methods are absent."""
        return self._request("post",path,params=params,json=json,profile_id=profile_id)
    def _request(self,method,path,params=None,json=None,profile_id=None):
        url=f"{self._settings.require_auth().base_url}/{path.lstrip('/')}";headers=self.headers(profile_id);last_error=None
        for attempt in range(self._max_attempts):
            try:response=getattr(self._session,method)(url,params=params,json=json,headers=headers,timeout=self._timeout)
            except requests.Timeout:error=AdsApiClientError(None,"Amazon Ads request timed out",True)
            except requests.RequestException:error=AdsApiClientError(None,"Amazon Ads request failed",True)
            else:
                if response.ok:
                    try:return response.json()
                    except ValueError as error:raise AdsApiClientError(response.status_code,"Amazon Ads returned invalid JSON") from error
                error=self._normalize_error(response.status_code)
            last_error=error
            if not error.retryable or attempt==self._max_attempts-1:raise error
            sleep(.25*(2**attempt))
        raise last_error or AdsApiClientError(None,"Amazon Ads request failed")
    @staticmethod
    def _normalize_error(status):
        messages={401:("Amazon Ads authorization is invalid or expired",False),403:("Amazon Ads access is not permitted",False),404:("Amazon Ads resource was not found",False),429:("Amazon Ads rate limit reached",True),500:("Amazon Ads service error",True),502:("Amazon Ads service error",True),503:("Amazon Ads service unavailable",True),504:("Amazon Ads service unavailable",True)}
        message,retryable=messages.get(status,("Amazon Ads API request failed",False));return AdsApiClientError(status,message,retryable)