"""Immutable metadata-only Amazon Ads advertiser target resolution."""
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib


@dataclass(frozen=True)
class AdsResolvedAdvertiserTarget:
    ad_product: str
    advertiser_entity_type: str
    advertiser_entity_id: str
    mutation_kind: str
    campaign_id: str | None = None
    ad_group_id: str | None = None


@dataclass(frozen=True)
class AdsWriteTargetResolution:
    target_resolution_id: str
    write_intent_id: str
    seller_id: str
    marketplace_id: str
    profile_id: str
    recommendation_id: str | None
    execution_plan_id: str | None
    action_type: str | None
    direction: str | None
    scope_type: str | None
    scope_id: str | None
    ad_product: str | None
    advertiser_entity_type: str | None
    advertiser_entity_id: str | None
    campaign_id: str | None
    ad_group_id: str | None
    mutation_kind: str | None
    status: str
    eligible: bool
    source: str
    safety_checks: tuple[dict[str, object], ...]
    created_at: datetime

    @classmethod
    def create(cls, intent_id, seller, marketplace, profile, status, eligible,
               checks, created_at, intent=None, target=None):
        values=(seller,marketplace,str(profile),intent_id,getattr(intent,"action_type",None),
            getattr(intent,"direction",None),getattr(intent,"scope_type",None),getattr(intent,"scope_id",None),
            getattr(target,"ad_product",None),getattr(target,"advertiser_entity_type",None),
            getattr(target,"advertiser_entity_id",None),getattr(target,"campaign_id",None),
            getattr(target,"ad_group_id",None),getattr(target,"mutation_kind",None))
        identifier=hashlib.sha256("|".join(str(v) for v in values).encode("utf-8")).hexdigest()[:24]
        return cls(identifier,intent_id,seller,marketplace,str(profile),
            getattr(intent,"recommendation_id",None),getattr(intent,"execution_plan_id",None),
            getattr(intent,"action_type",None),getattr(intent,"direction",None),
            getattr(intent,"scope_type",None),getattr(intent,"scope_id",None),
            getattr(target,"ad_product",None),getattr(target,"advertiser_entity_type",None),
            getattr(target,"advertiser_entity_id",None),getattr(target,"campaign_id",None),
            getattr(target,"ad_group_id",None),getattr(target,"mutation_kind",None),
            status,eligible,"trusted_advertiser_target_resolver",tuple(checks),created_at)

    def public_dict(self):
        result=asdict(self);result["safety_checks"]=list(self.safety_checks);result["created_at"]=self.created_at.isoformat();return result
