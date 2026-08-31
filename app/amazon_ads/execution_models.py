"""Dry-run-only Amazon Ads execution-plan models."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json


@dataclass(frozen=True)
class AdsExecutionPlan:
    recommendation_id: str
    decision_id: str | None
    seller_id: str
    marketplace_id: str
    profile_id: str
    scope_type: str
    scope_id: str
    recommendation_code: str
    action_type: str
    direction: str = "none"
    current_value: str | None = None
    proposed_value: str | None = None
    dry_run: bool = True
    eligible: bool = False
    status: str = "error"
    eligibility_code: str = "error"
    eligibility_reason: str = "Execution planning is unavailable."
    safety_checks: tuple[dict[str, object], ...] = ()
    created_at: datetime | None = None
    execution_plan_id: str | None = None

    @property
    def plan_hash(self) -> str:
        value = (self.seller_id, self.marketplace_id, self.profile_id, self.recommendation_id, self.action_type, self.direction)
        return hashlib.sha256("|".join(value).encode("utf-8")).hexdigest()

    @property
    def stable_execution_plan_id(self) -> str:
        return self.execution_plan_id or self.plan_hash[:24]

    def public_dict(self) -> dict[str, object]:
        return {"execution_plan_id":self.stable_execution_plan_id,"recommendation_id":self.recommendation_id,"decision_id":self.decision_id,"scope_type":self.scope_type,"scope_id":self.scope_id,"recommendation_code":self.recommendation_code,"action_type":self.action_type,"direction":self.direction,"current_value":self.current_value,"proposed_value":self.proposed_value,"dry_run":True,"eligible":self.eligible,"status":self.status,"eligibility_code":self.eligibility_code,"eligibility_reason":self.eligibility_reason,"safety_checks":list(self.safety_checks),"created_at":(self.created_at or datetime.now(timezone.utc)).isoformat()}
