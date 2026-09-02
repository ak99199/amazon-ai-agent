"""Immutable, secret-free internal Amazon Ads write-intent records."""
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib


@dataclass(frozen=True)
class AdsWriteIntent:
    write_intent_id: str
    idempotency_key: str
    execution_plan_id: str
    recommendation_id: str
    decision_id: str
    proposal_id: str
    preflight_id: str
    seller_id: str
    marketplace_id: str
    profile_id: str
    scope_type: str
    scope_id: str
    recommendation_code: str
    action_type: str
    direction: str
    current_value: str
    proposed_value: str
    currency: str | None
    status: str
    created_at: datetime
    source: str = "controlled_preflight"
    schema_version: int = 1

    @classmethod
    def prepared(cls, plan, proposal, preflight, created_at):
        parts = (plan.seller_id, plan.marketplace_id, str(plan.profile_id),
                 plan.stable_execution_plan_id, plan.recommendation_id,
                 plan.decision_id, proposal.proposal_id, preflight.preflight_id,
                 plan.scope_type, plan.scope_id, plan.action_type, plan.direction,
                 proposal.current_value, proposal.proposed_value)
        key = hashlib.sha256("|".join(str(value) for value in parts).encode("utf-8")).hexdigest()
        return cls(key[:24], key, plan.stable_execution_plan_id,
                   plan.recommendation_id, plan.decision_id, proposal.proposal_id,
                   preflight.preflight_id, plan.seller_id, plan.marketplace_id,
                   str(plan.profile_id), plan.scope_type, plan.scope_id,
                   plan.recommendation_code, plan.action_type, plan.direction,
                   proposal.current_value, proposal.proposed_value,
                   proposal.currency, "prepared", created_at)

    def public_dict(self):
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        return result


class AdsWriteIntentBlockedError(ValueError):
    def __init__(self, status):
        self.status = status
        super().__init__(status)


@dataclass(frozen=True)
class AdsWriteIntentLifecycleResult:
    write_intent_id: str
    status: str
    reason_code: str
    revalidated_at: datetime
    safety_checks: tuple[dict[str, object], ...] = ()

    def public_dict(self):
        return {"write_intent_id": self.write_intent_id, "status": self.status,
                "reason_code": self.reason_code,
                "revalidated_at": self.revalidated_at.isoformat(),
                "safety_checks": list(self.safety_checks)}
