from dataclasses import dataclass
from os import getenv
from dotenv import load_dotenv
load_dotenv()
SP_API_ENDPOINT = "https://sellingpartnerapi-eu.amazon.com"
INDIA_MARKETPLACE_ID = "A21TJRUUN4KGV"
class ConfigurationError(Exception): pass
@dataclass(frozen=True)
class Settings:
    client_id: str | None
    client_secret: str | None
    refresh_token: str | None
    seller_id: str | None
    marketplace_id: str | None
    @classmethod
    def from_environment(cls):
        return cls(getenv("AMAZON_SP_API_CLIENT_ID") or None, getenv("AMAZON_SP_API_CLIENT_SECRET") or None, getenv("AMAZON_SP_REFRESH_TOKEN") or None, getenv("AMAZON_SELLER_ID") or None, getenv("AMAZON_MARKETPLACE_ID") or None)
    @property
    def missing_fields(self):
        values={"AMAZON_SP_API_CLIENT_ID":self.client_id,"AMAZON_SP_API_CLIENT_SECRET":self.client_secret,"AMAZON_SP_REFRESH_TOKEN":self.refresh_token,"AMAZON_SELLER_ID":self.seller_id,"AMAZON_MARKETPLACE_ID":self.marketplace_id}
        return tuple(key for key,value in values.items() if not value)
    def require_complete(self):
        if self.missing_fields: raise ConfigurationError("Amazon listing connection is not configured")
        return self
