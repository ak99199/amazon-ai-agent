"""Configuration isolated from Selling Partner API credentials."""
from dataclasses import dataclass
from os import getenv
ADS_REGION_ENDPOINTS={"NA":"https://advertising-api.amazon.com","EU":"https://advertising-api-eu.amazon.com","FE":"https://advertising-api-fe.amazon.com"}
class AdsConfigurationError(Exception): pass
@dataclass(frozen=True)
class AdsSettings:
    client_id:str|None; client_secret:str|None; refresh_token:str|None; profile_id:str|None; region:str="FE"
    @classmethod
    def from_environment(cls):
        region=(getenv("AMAZON_ADS_REGION") or "FE").upper()
        return cls(getenv("AMAZON_ADS_CLIENT_ID") or None,getenv("AMAZON_ADS_CLIENT_SECRET") or None,getenv("AMAZON_ADS_REFRESH_TOKEN") or None,getenv("AMAZON_ADS_PROFILE_ID") or None,region)
    @property
    def base_url(self):
        try:return ADS_REGION_ENDPOINTS[self.region]
        except KeyError as error:raise AdsConfigurationError("Amazon Ads region is not configured") from error
    @property
    def missing_auth_fields(self):return tuple(name for name,value in (("AMAZON_ADS_CLIENT_ID",self.client_id),("AMAZON_ADS_CLIENT_SECRET",self.client_secret),("AMAZON_ADS_REFRESH_TOKEN",self.refresh_token)) if not value)
    def require_auth(self):
        if self.missing_auth_fields:raise AdsConfigurationError("Amazon Ads authentication is not configured")
        self.base_url;return self
    def require_profile_api(self):
        self.require_auth()
        if not self.profile_id:raise AdsConfigurationError("Amazon Ads profile API is not configured")
        return self