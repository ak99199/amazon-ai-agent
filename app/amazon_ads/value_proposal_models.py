"""Immutable, secret-free models for controlled exact-value proposals."""
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import os


@dataclass(frozen=True)
class AdsValueProposalConfig:
    """Bid proposal percentage; zero disables proposal generation."""

    bid_proposal_percent: Decimal = Decimal("0")
    valid: bool = True

    @classmethod
    def from_environment(cls):
        raw = os.getenv("AMAZON_ADS_BID_PROPOSAL_PERCENT")
        if raw in (None, ""):
            return cls()
        try:
            value = Decimal(raw)
        except (InvalidOperation, ValueError):
            return cls(valid=False)
        if not value.is_finite() or value < 0:
            return cls(valid=False)
        return cls(value, True)


@dataclass(frozen=True)
class AdsExactValueProposal:
    proposal_id: str
    execution_plan_id: str
    recommendation_id: str | None
    decision_id: str | None
    seller_id: str
    marketplace_id: str
    profile_id: str
    scope_type: str | None
    scope_id: str | None
    action_type: str | None
    direction: str | None
    current_value: str | None
    proposed_value: str | None
    currency: str | None
    proposal_status: str
    eligible: bool
    source: str
    safety_checks: tuple[dict[str, object], ...]
    created_at: datetime

    @classmethod
    def create(cls, plan_id, seller, marketplace, profile, status, eligible,
               checks, created_at, plan=None, current=None, proposed=None,
               percent=None, currency=None):
        basis = "|".join((seller, marketplace, str(profile), plan_id,
                          str(getattr(plan, "recommendation_id", None)),
                          str(getattr(plan, "action_type", None)),
                          str(getattr(plan, "direction", None)), str(current),
                          str(percent), str(proposed)))
        identifier = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
        return cls(identifier, plan_id,
                   getattr(plan, "recommendation_id", None),
                   getattr(plan, "decision_id", None), seller, marketplace,
                   str(profile), getattr(plan, "scope_type", None),
                   getattr(plan, "scope_id", None),
                   getattr(plan, "action_type", None),
                   getattr(plan, "direction", None),
                   str(current) if current is not None else None,
                   str(proposed) if proposed is not None else None, currency,
                   status, eligible, "trusted_current_value_provider",
                   tuple(checks), created_at)

    def public_dict(self):
        result = asdict(self)
        result["safety_checks"] = list(self.safety_checks)
        result["created_at"] = self.created_at.isoformat()
        return result
