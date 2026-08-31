"""Normalized Amazon Ads data models without raw API payload exposure."""
from dataclasses import dataclass
@dataclass(frozen=True)
class AdsAccessToken:
    access_token:str; token_type:str; expires_in:int
@dataclass(frozen=True)
class AdsProfile:
    profile_id:str; country_code:str|None=None; currency_code:str|None=None; timezone:str|None=None; account_info:dict|None=None; account_id:str|None=None; account_type:str|None=None; marketplace_string_id:str|None=None
    @classmethod
    def from_api(cls,raw):
        account=raw.get("accountInfo") if isinstance(raw.get("accountInfo"),dict) else None
        profile_id=raw.get("profileId")
        if profile_id is None:raise ValueError("Amazon Ads profile response is invalid")
        return cls(str(profile_id),raw.get("countryCode") if isinstance(raw.get("countryCode"),str) else None,raw.get("currencyCode") if isinstance(raw.get("currencyCode"),str) else None,raw.get("timezone") if isinstance(raw.get("timezone"),str) else None,account,str(raw.get("accountId")) if raw.get("accountId") is not None else (str(account.get("id")) if account and account.get("id") is not None else None),raw.get("accountType") if isinstance(raw.get("accountType"),str) else (account.get("type") if account and isinstance(account.get("type"),str) else None),raw.get("marketplaceStringId") if isinstance(raw.get("marketplaceStringId"),str) else None)
@dataclass(frozen=True)
class AdsApiErrorResponse:
    status_code:int|None; message:str; retryable:bool=False