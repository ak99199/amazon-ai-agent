"""Prepares persisted Ads write intents; deliberately has no mutation transport."""
from datetime import datetime, timezone
from decimal import Decimal, DecimalException

from app.amazon_ads.write_intent_models import AdsWriteIntent, AdsWriteIntentBlockedError
from app.amazon_ads.write_models import AdsWriteConfig
from app.services.ads_execution_safety_service import AdsExecutionSafetyService


class AdsWriteIntentService:
    def __init__(self, recommendation_service, repository, write_config=None,
                 approval_status="pending", safety_service=None, now=None):
        self.recommendations = recommendation_service
        self.repository = repository
        self.write_config = write_config or AdsWriteConfig.from_environment()
        self.approval_status = str(approval_status or "pending").lower()
        self.safety = safety_service or AdsExecutionSafetyService()
        self.now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _block(status):
        raise AdsWriteIntentBlockedError(status)

    def prepare(self, seller, marketplace, profile, execution_plan_id,
                confirm=False, proposal=None, preflight=None, window=30):
        profile = str(profile)
        if confirm is not True:
            self._block("confirmation_required")
        if not self.write_config.valid or not self.write_config.enabled:
            self._block("write_disabled")
        if not self.write_config.dry_run_only:
            self._block("dry_run_only_required")
        if self.approval_status != "approved":
            self._block("approval_pending")
        plans = self.repository.list_execution_plans(seller, marketplace, profile, 200)
        plan = next((item for item in plans if item.stable_execution_plan_id == execution_plan_id), None)
        if plan is None:
            self._block("plan_not_found")
        decision = self.repository.get_decision(seller, marketplace, profile, plan.recommendation_id)
        if not (decision and decision.status == "approved" and
                decision.stable_decision_id == plan.decision_id):
            self._block("decision_not_approved")
        if plan.eligible is not True:
            self._block("plan_not_eligible")
        if plan.dry_run is not True:
            self._block("plan_not_dry_run")
        if not (plan.seller_id == seller and plan.marketplace_id == marketplace and
                str(plan.profile_id) == profile):
            self._block("scope_mismatch")
        current = next((item for item in self.recommendations.get_recommendations(
            seller, marketplace, profile, window) if item.recommendation_id == plan.recommendation_id), None)
        if not (current and current.recommendation_code == plan.recommendation_code and
                current.scope_type == plan.scope_type and current.scope_id == plan.scope_id):
            self._block("stale_recommendation")
        if proposal is None:
            self._block("proposal_required")
        if proposal.eligible is not True or proposal.proposal_status != "eligible_proposal":
            self._block("proposal_not_eligible")
        proposal_plan = (proposal.execution_plan_id == execution_plan_id and
                         proposal.recommendation_id == plan.recommendation_id and
                         proposal.seller_id == seller and proposal.marketplace_id == marketplace and
                         proposal.profile_id == profile and proposal.scope_type == plan.scope_type and
                         proposal.scope_id == plan.scope_id and proposal.action_type == plan.action_type and
                         proposal.direction == plan.direction)
        if not proposal_plan:
            self._block("proposal_plan_mismatch")
        if proposal.decision_id != decision.stable_decision_id:
            self._block("proposal_decision_mismatch")
        if preflight is None:
            self._block("preflight_required")
        if preflight.eligible is not True or preflight.status != "eligible_preflight":
            self._block("preflight_not_eligible")
        preflight_match = (preflight.execution_plan_id == execution_plan_id and
            preflight.recommendation_id == plan.recommendation_id and
            preflight.decision_id == decision.stable_decision_id and
            preflight.seller_id == seller and preflight.marketplace_id == marketplace and
            preflight.profile_id == profile and preflight.scope_type == plan.scope_type and
            preflight.scope_id == plan.scope_id and preflight.action_type == plan.action_type and
            preflight.direction == plan.direction and preflight.proposal_id == proposal.proposal_id)
        if not preflight_match:
            self._block("preflight_plan_mismatch")
        if plan.action_type != "BID_DIRECTION_REVIEW":
            self._block("unsupported_action")
        if preflight.current_value != proposal.current_value:
            self._block("current_value_mismatch")
        if preflight.proposed_value != proposal.proposed_value:
            self._block("proposed_value_mismatch")
        expected = {"BID_INCREASE_CANDIDATE": "increase",
                    "BID_DECREASE_CANDIDATE": "decrease"}.get(plan.recommendation_code)
        if not (plan.direction == expected and
                getattr(current, "suggested_bid_direction", None) == plan.direction):
            self._block("invalid_direction")
        if not self._hard_limits(proposal):
            self._block("hard_limit_violation")
        intent = AdsWriteIntent.prepared(plan, proposal, preflight, self.now())
        return self.repository.save_write_intent(intent)

    def list_intents(self, seller, marketplace, profile, status=None, limit=50):
        if status not in (None, "prepared", "superseded", "cancelled"):
            raise ValueError("Unsupported write-intent status")
        return self.repository.list_write_intents(seller, marketplace, str(profile), status, limit)

    def _hard_limits(self, proposal):
        try:
            current = Decimal(proposal.current_value)
            proposed = Decimal(proposal.proposed_value)
            if (not current.is_finite() or not proposed.is_finite() or
                    current <= 0 or proposed <= 0):
                return False
            maximum = (self.safety.config.max_bid_increase_percent
                       if proposal.direction == "increase"
                       else self.safety.config.max_bid_decrease_percent)
            consistent = proposed > current if proposal.direction == "increase" else proposed < current
            return (consistent and self.safety.percentage_within_limit(current, proposed, maximum) and
                    self.safety.config.max_single_action_amount > 0 and
                    proposed <= self.safety.config.max_single_action_amount and
                    self.safety.config.max_actions_per_run >= 1)
        except (DecimalException, ValueError, TypeError):
            return False
