"""Immutable, payload-free sealed Amazon Ads write-command metadata."""
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, DecimalException
import hashlib
import json


def canonical_decimal(value):
    try:value=Decimal(str(value))
    except (DecimalException,ValueError,TypeError) as error:raise ValueError("Invalid command value") from error
    if not value.is_finite():raise ValueError("Invalid command value")
    result=format(value.normalize(),"f")
    return "0" if result in ("-0","0") else result


@dataclass(frozen=True)
class AdsSealedWriteCommand:
    command_id:str;command_hash:str;write_intent_id:str;target_resolution_id:str
    execution_plan_id:str;recommendation_id:str;decision_id:str;proposal_id:str;preflight_id:str
    seller_id:str;marketplace_id:str;profile_id:str;ad_product:str
    advertiser_entity_type:str;advertiser_entity_id:str;campaign_id:str|None;ad_group_id:str|None
    action_type:str;mutation_kind:str;direction:str;expected_current_value:str;proposed_value:str
    currency:str|None;status:str;created_at:datetime;schema_version:int=1;source:str="sealed_internal_command"

    @classmethod
    def seal(cls,intent,target,created_at):
        current=canonical_decimal(intent.current_value);proposed=canonical_decimal(intent.proposed_value)
        ordered=(intent.seller_id,intent.marketplace_id,intent.profile_id,intent.write_intent_id,
            target.target_resolution_id,intent.execution_plan_id,intent.recommendation_id,intent.decision_id,
            intent.proposal_id,intent.preflight_id,target.ad_product,target.advertiser_entity_type,
            target.advertiser_entity_id,target.campaign_id,target.ad_group_id,intent.action_type,
            target.mutation_kind,intent.direction,current,proposed,intent.currency,1)
        canonical=json.dumps(ordered,ensure_ascii=False,separators=(",",":"))
        digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(digest[:24],digest,intent.write_intent_id,target.target_resolution_id,
            intent.execution_plan_id,intent.recommendation_id,intent.decision_id,intent.proposal_id,
            intent.preflight_id,intent.seller_id,intent.marketplace_id,intent.profile_id,target.ad_product,
            target.advertiser_entity_type,target.advertiser_entity_id,target.campaign_id,target.ad_group_id,
            intent.action_type,target.mutation_kind,intent.direction,current,proposed,intent.currency,"sealed",created_at)

    def public_dict(self):
        result=asdict(self);result["created_at"]=self.created_at.isoformat();return result


class AdsSealedWriteCommandBlockedError(ValueError):
    def __init__(self,status):self.status=status;super().__init__(status)
