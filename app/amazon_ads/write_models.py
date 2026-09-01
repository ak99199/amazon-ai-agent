"""Immutable, secret-free models for no-transport Ads write preflight."""
from dataclasses import asdict,dataclass
from datetime import datetime
import hashlib

@dataclass(frozen=True)
class AdsWriteConfig:
    enabled:bool=False
    dry_run_only:bool=True
    valid:bool=True
    @classmethod
    def from_environment(cls):
        from os import getenv
        def value(name,default):
            raw=getenv(name)
            if raw in (None,""):return default,True
            normalized=raw.strip().lower()
            return (normalized=="true",normalized in ("true","false"))
        enabled,enabled_valid=value("AMAZON_ADS_WRITE_ENABLED",False);dry,dry_valid=value("AMAZON_ADS_WRITE_DRY_RUN_ONLY",True)
        return cls(enabled if enabled_valid else False,dry if dry_valid else True,enabled_valid and dry_valid)

@dataclass(frozen=True)
class AdsWritePreflight:
    preflight_id:str;execution_plan_id:str;recommendation_id:str|None;decision_id:str|None;seller_id:str;marketplace_id:str;profile_id:str;scope_type:str|None;scope_id:str|None;recommendation_code:str|None;action_type:str|None;direction:str|None;status:str;eligible:bool;dry_run:bool;safety_checks:tuple[dict[str,object],...];created_at:datetime
    @classmethod
    def create(cls,plan_id,seller,marketplace,profile,status,eligible,checks,created_at,plan=None):
        basis="|".join((seller,marketplace,str(profile),plan_id,status,str(getattr(plan,"decision_id",None)),str(getattr(plan,"action_type",None)),str(getattr(plan,"direction",None)),str(getattr(plan,"current_value",None)),str(getattr(plan,"proposed_value",None))));identifier=hashlib.sha256(basis.encode()).hexdigest()[:24]
        return cls(identifier,plan_id,getattr(plan,"recommendation_id",None),getattr(plan,"decision_id",None),seller,marketplace,str(profile),getattr(plan,"scope_type",None),getattr(plan,"scope_id",None),getattr(plan,"recommendation_code",None),getattr(plan,"action_type",None),getattr(plan,"direction",None),status,eligible,True,tuple(checks),created_at)
    def public_dict(self):
        result=asdict(self);result["created_at"]=self.created_at.isoformat();result["safety_checks"]=list(self.safety_checks);return result
