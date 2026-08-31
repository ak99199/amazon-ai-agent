from time import sleep
import requests
from app.config import SP_API_ENDPOINT
class AmazonClientError(Exception):
    def __init__(self,status_code,message,retryable=False): super().__init__(message); self.status_code=status_code; self.retryable=retryable
class AmazonSPAPIClient:
    def __init__(self,authenticator,session=None,max_attempts=3): self._authenticator=authenticator; self._session=session or requests.Session(); self._max_attempts=max_attempts
    def get(self,path,params=None):
        token=self._authenticator.get_access_token(); url=f"{SP_API_ENDPOINT}/{path.lstrip('/')}"; headers={"x-amz-access-token":token,"accept":"application/json"}; last_error=None
        for attempt in range(self._max_attempts):
            try: response=self._session.get(url,params=params,headers=headers,timeout=30)
            except requests.Timeout: error=AmazonClientError(None,"Amazon request timed out",True)
            except requests.RequestException: error=AmazonClientError(None,"Amazon request failed",True)
            else:
                if response.ok:
                    try: payload=response.json()
                    except ValueError as error: raise AmazonClientError(response.status_code,"Amazon returned invalid JSON") from error
                    if not isinstance(payload,dict): raise AmazonClientError(response.status_code,"Amazon returned invalid JSON")
                    return payload
                error=self._normalize_error(response.status_code)
            last_error=error
            if not error.retryable or attempt==self._max_attempts-1: raise error
            sleep(.25*(2**attempt))
        raise last_error or AmazonClientError(None,"Amazon request failed")
    @staticmethod
    def _normalize_error(status):
        messages={401:("Amazon authorization is invalid or expired",False),403:("Amazon access is not permitted",False),404:("Amazon resource was not found",False),429:("Amazon rate limit reached",True),500:("Amazon service error",True),502:("Amazon service error",True),503:("Amazon service unavailable",True)}
        message,retryable=messages.get(status,("Amazon API request failed",False)); return AmazonClientError(status,message,retryable)
