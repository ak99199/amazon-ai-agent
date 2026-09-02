"""Deterministic bid proposals only; this module has no Amazon transport."""
from datetime import datetime, timezone
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from typing import Protocol

from app.amazon_ads.value_proposal_models import AdsExactValueProposal, AdsValueProposalConfig
from app.amazon_ads.write_models import AdsWriteConfig
from app.services.ads_execution_safety_service import AdsExecutionSafetyService


class AdsCurrentValueProvider(Protocol):
    def resolve_current_value(self, seller_id, marketplace_id, profile_id, plan): ...


class AdsExactValueProposalService:
    """Creates two-decimal bid proposals from authoritative current values."""

    QUANTUM = Decimal("0.01")

    def __init__(self, recommendation_service, repository, current_value_provider=None,
                 config=None, safety_service=None, write_config=None, now=None):
        self.recommendations = recommendation_service
        self.repository = repository
        self.provider = current_value_provider
        self.config = config or AdsValueProposalConfig.from_environment()
        self.safety = safety_service or AdsExecutionSafetyService()
        self.write_config = write_config or AdsWriteConfig.from_environment()
        self.now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _check(name, passed, reason):
        return {"name": name, "passed": bool(passed), "reason": reason}

    def propose(self, seller, marketplace, profile, execution_plan_id,
                confirm=False, window=30):
        profile = str(profile)
        plan = None
        checks = []

        def add(name, passed, reason):
            checks.append(self._check(name, passed, reason))
            return passed

        def stop(status, current=None, proposed=None):
            return AdsExactValueProposal.create(execution_plan_id, seller,
                marketplace, profile, status, False, checks, self.now(), plan,
                current, proposed, self.config.bid_proposal_percent)

        if not add("EXPLICIT_CONFIRMATION", confirm is True,
                   "Explicit exact-value proposal confirmation is required."):
            return stop("confirmation_required")
        if not add("PROPOSAL_CONFIGURATION", self.config.valid,
                   "Bid proposal configuration is valid."):
            return stop("proposal_configuration_invalid")
        percent = self.config.bid_proposal_percent
        if not add("PROPOSAL_PERCENT_CONFIGURED", percent > 0,
                   "A positive bid proposal percentage is configured."):
            return stop("proposal_percent_not_configured")
        if not add("WRITE_DRY_RUN_ONLY", self.write_config.valid and self.write_config.dry_run_only,
                   "Dry-run-only write safety is enforced."):
            return stop("dry_run_only_required")
        plans = self.repository.list_execution_plans(seller, marketplace, profile, 200)
        plan = next((item for item in plans if item.stable_execution_plan_id == execution_plan_id), None)
        if not add("CURRENT_EXECUTION_PLAN", bool(plan),
                   "Execution plan exists in the authoritative scope."):
            return stop("plan_not_found")
        decision = self.repository.get_decision(seller, marketplace, profile, plan.recommendation_id)
        approved = bool(decision and decision.status == "approved" and
                        decision.stable_decision_id == plan.decision_id)
        if not add("APPROVED_DECISION", approved, "Stored decision remains approved."):
            return stop("decision_not_approved")
        if not add("PLAN_ELIGIBLE", plan.eligible is True, "Execution plan remains eligible."):
            return stop("plan_not_eligible")
        if not add("PLAN_DRY_RUN", plan.dry_run is True, "Execution plan is dry-run only."):
            return stop("plan_not_eligible")
        matches = (plan.seller_id == seller, plan.marketplace_id == marketplace,
                   str(plan.profile_id) == profile)
        add("SELLER_MATCH", matches[0], "Seller scope matches.")
        add("MARKETPLACE_MATCH", matches[1], "Marketplace scope matches.")
        add("PROFILE_MATCH", matches[2], "Profile scope matches.")
        if not all(matches):
            return stop("scope_mismatch")
        current_recommendation = next((item for item in self.recommendations.get_recommendations(
            seller, marketplace, profile, window) if item.recommendation_id == plan.recommendation_id), None)
        unchanged = bool(current_recommendation and
            current_recommendation.recommendation_code == plan.recommendation_code and
            current_recommendation.scope_type == plan.scope_type and
            current_recommendation.scope_id == plan.scope_id)
        if not add("CURRENT_RECOMMENDATION", unchanged,
                   "Recommendation remains current and unchanged."):
            return stop("stale_recommendation")
        expected_direction = {"BID_INCREASE_CANDIDATE": "increase",
                              "BID_DECREASE_CANDIDATE": "decrease"}.get(plan.recommendation_code)
        if not add("SUPPORTED_ACTION", plan.action_type == "BID_DIRECTION_REVIEW" and
                   expected_direction is not None,
                   "Only bid-direction reviews support exact values."):
            return stop("exact_value_not_applicable")
        direction_valid = (plan.direction in ("increase", "decrease") and
                           plan.direction == expected_direction and
                           getattr(current_recommendation, "suggested_bid_direction", None) == plan.direction)
        if not add("VALID_DIRECTION", direction_valid,
                   "Bid direction exactly matches the current recommendation."):
            return stop("invalid_direction")
        maximum = (self.safety.config.max_bid_increase_percent if plan.direction == "increase"
                   else self.safety.config.max_bid_decrease_percent)
        if not add("PERCENTAGE_HARD_LIMIT", percent <= maximum,
                   "Proposal percentage is within the configured hard limit."):
            return stop("hard_limit_violation")
        if not add("MAX_ACTIONS_PER_RUN", self.safety.config.max_actions_per_run >= 1,
                   "At least one action is allowed per run."):
            return stop("hard_limit_violation")
        if not add("TRUSTED_CURRENT_VALUE_PROVIDER", self.provider is not None,
                   "A trusted current-value provider is available."):
            return stop("current_value_unavailable")
        try:
            current = Decimal(str(self.provider.resolve_current_value(seller, marketplace, profile, plan)))
        except Exception:
            current = None
        if not add("CURRENT_VALUE", bool(current is not None and current.is_finite() and current > 0),
                   "Trusted current bid is finite and positive."):
            return stop("current_value_unavailable", current)
        try:
            factor = Decimal("1") + (percent / Decimal("100")) * (Decimal("1") if plan.direction == "increase" else Decimal("-1"))
            proposed = (current * factor).quantize(self.QUANTUM, rounding=ROUND_HALF_UP)
        except (DecimalException, ValueError, TypeError):
            return stop("invalid_proposed_value", current)
        proposed_valid = proposed.is_finite() and proposed > 0
        if not add("PROPOSED_VALUE", proposed_valid, "Proposed bid is finite and positive."):
            return stop("invalid_proposed_value", current, proposed)
        consistent = proposed > current if plan.direction == "increase" else proposed < current
        if not add("DIRECTION_CONSISTENCY", consistent,
                   "Proposed bid follows the approved recommendation direction."):
            return stop("direction_inconsistent", current, proposed)
        try:
            within = self.safety.percentage_within_limit(current, proposed, maximum)
        except (DecimalException, ValueError, TypeError):
            within = False
        amount_ok = (self.safety.config.max_single_action_amount > 0 and
                     proposed <= self.safety.config.max_single_action_amount)
        if not add("HARD_LIMITS", within and amount_ok,
                   "Proposed bid remains within percentage and amount limits."):
            return stop("hard_limit_violation", current, proposed)
        return AdsExactValueProposal.create(execution_plan_id, seller, marketplace,
            profile, "eligible_proposal", True, checks, self.now(), plan, current,
            proposed, percent)
