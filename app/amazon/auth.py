import requests
from app.config import ConfigurationError, Settings
LWA_TOKEN_ENDPOINT="https://api.amazon.com/auth/o2/token"
class AuthenticationError(Exception): pass
class LwaAuthenticator:
    def __init__(self, settings: Settings, session=None): self._settings=settings; self._session=session or requests.Session()
    def get_access_token(self):
        try: settings=self._settings.require_complete()
        except ConfigurationError as error: raise AuthenticationError("Amazon authentication is not configured") from error
        try:
            response=self._session.post(LWA_TOKEN_ENDPOINT,data={"grant_type":"refresh_token","refresh_token":settings.refresh_token,"client_id":settings.client_id,"client_secret":settings.client_secret},timeout=30)
        except requests.Timeout as error: raise AuthenticationError("Amazon authentication timed out") from error
        except requests.RequestException as error: raise AuthenticationError("Amazon authentication request failed") from error
        if not response.ok: raise AuthenticationError("Amazon authentication was rejected")
        try: token=response.json().get("access_token")
        except ValueError as error: raise AuthenticationError("Amazon authentication returned invalid JSON") from error
        if not isinstance(token,str) or not token: raise AuthenticationError("Amazon authentication returned an invalid response")
        return token
