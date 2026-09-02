"""Authoritative write-intent lifecycle checks; contains no Amazon transport."""
from datetime import datetime, timezone
from decimal import Decimal, DecimalException

from app.amazon_ads.write_intent_models import AdsWriteIntentLifecycleResult
from app.amazon_ads.write_models import AdsWriteConfig
from app.services.ads_execution_safety_service import AdsExecutionSafetyService


class AdsWriteIntentRevalidationService:
    def __init__(self, recommendation_service, repository, proposal_resolver=None,
                 preflight_resolver=None, write_config=None, approval_status="pending",
                 safety_service=None, now=None):
        self.recommendations=recommendation_service;self.repository=repository
        self.proposal_resolver=proposal_resolver;self.preflight_resolver=preflight_resolver
        self.write_config=write_config or AdsWriteConfig.from_environment()
        self.approval_status=str(approval_status or "pending").lower()
        self.safety=safety_service or AdsExecutionSafetyService()
        self.now=now or (lambda:datetime.now(timezone.utc))

    @staticmethod
    def _check(name,passed):return {"name":name,"passed":bool(passed)}

    def revalidate(self,seller,marketplace,profile,write_intent_id,confirm=False,window=30):
        profile=str(profile);checks=[];at=self.now()
        if confirm is not True:return self._result(write_intent_id,"blocked","confirmation_required",at,checks)
        intent=self.repository.get_write_intent(seller,marketplace,profile,write_intent_id)
        if intent is None:return self._result(write_intent_id,"not_found","intent_not_found",at,checks)
        if intent.status!="prepared":return self._result(write_intent_id,intent.status,"intent_not_prepared",at,checks)
        def require(name,passed,reason):
            checks.append(self._check(name,passed))
            if not passed:return self._supersede(intent,reason,at,checks)
        result=require("SCOPE",intent.seller_id==seller and intent.marketplace_id==marketplace and intent.profile_id==profile,"scope_mismatch")
        if result:return result
        result=require("WRITE_ENABLED",self.write_config.valid and self.write_config.enabled,"write_disabled")
        if result:return result
        result=require("DRY_RUN_ONLY",self.write_config.dry_run_only,"dry_run_only_required")
        if result:return result
        result=require("APPROVAL",self.approval_status=="approved","approval_pending")
        if result:return result
        plans=self.repository.list_execution_plans(seller,marketplace,profile,200)
        plan=next((p for p in plans if p.stable_execution_plan_id==intent.execution_plan_id),None)
        result=require("PLAN_EXISTS",plan is not None,"plan_missing")
        if result:return result
        result=require("PLAN_ELIGIBLE",plan.eligible is True,"plan_not_eligible")
        if result:return result
        result=require("PLAN_DRY_RUN",plan.dry_run is True,"plan_not_dry_run")
        if result:return result
        plan_match=(plan.recommendation_id==intent.recommendation_id and plan.decision_id==intent.decision_id and plan.scope_type==intent.scope_type and plan.scope_id==intent.scope_id and plan.recommendation_code==intent.recommendation_code and plan.action_type==intent.action_type)
        result=require("PLAN_MATCH",plan_match,"stale_recommendation")
        if result:return result
        decision=self.repository.get_decision(seller,marketplace,profile,intent.recommendation_id)
        result=require("DECISION",bool(decision and decision.status=="approved" and decision.stable_decision_id==intent.decision_id),"decision_not_approved")
        if result:return result
        current=next((r for r in self.recommendations.get_recommendations(seller,marketplace,profile,window) if r.recommendation_id==intent.recommendation_id),None)
        rec_match=bool(current and current.recommendation_code==intent.recommendation_code and current.scope_type==intent.scope_type and current.scope_id==intent.scope_id)
        result=require("RECOMMENDATION",rec_match,"stale_recommendation")
        if result:return result
        expected={"BID_INCREASE_CANDIDATE":"increase","BID_DECREASE_CANDIDATE":"decrease"}.get(intent.recommendation_code)
        result=require("DIRECTION",intent.direction==plan.direction==expected and getattr(current,"suggested_bid_direction",None)==intent.direction,"invalid_direction")
        if result:return result
        try:proposal=self.proposal_resolver(intent) if self.proposal_resolver else None
        except Exception:proposal=None
        proposal_match=bool(proposal and proposal.eligible and proposal.proposal_id==intent.proposal_id and proposal.execution_plan_id==intent.execution_plan_id and proposal.decision_id==intent.decision_id)
        result=require("PROPOSAL",proposal_match,"proposal_mismatch")
        if result:return result
        result=require("CURRENT_VALUE",proposal.current_value==intent.current_value,"current_value_changed")
        if result:return result
        result=require("PROPOSED_VALUE",proposal.proposed_value==intent.proposed_value,"proposed_value_changed")
        if result:return result
        try:preflight=self.preflight_resolver(intent) if self.preflight_resolver else None
        except Exception:preflight=None
        preflight_match=bool(preflight and preflight.eligible and preflight.status=="eligible_preflight" and preflight.preflight_id==intent.preflight_id and preflight.proposal_id==intent.proposal_id and preflight.execution_plan_id==intent.execution_plan_id and preflight.current_value==intent.current_value and preflight.proposed_value==intent.proposed_value)
        result=require("PREFLIGHT",preflight_match,"preflight_mismatch")
        if result:return result
        result=require("HARD_LIMITS",self._hard_limits(intent),"hard_limit_violation")
        if result:return result
        return self._result(intent.write_intent_id,"prepared","current",at,checks)

    def cancel(self,seller,marketplace,profile,write_intent_id,confirm=False):
        at=self.now();intent=self.repository.get_write_intent(seller,marketplace,str(profile),write_intent_id)
        if confirm is not True:return self._result(write_intent_id,getattr(intent,"status","blocked"),"confirmation_required",at,())
        if intent is None:return self._result(write_intent_id,"not_found","intent_not_found",at,())
        if intent.status!="prepared":return self._result(write_intent_id,intent.status,"intent_not_prepared",at,())
        updated=self.repository.transition_write_intent(seller,marketplace,str(profile),write_intent_id,"cancelled","WRITE_INTENT_CANCELLED",at)
        return self._result(write_intent_id,getattr(updated,"status","not_found"),"cancelled" if updated else "intent_not_found",at,())

    def _supersede(self,intent,reason,at,checks):
        updated=self.repository.transition_write_intent(intent.seller_id,intent.marketplace_id,intent.profile_id,intent.write_intent_id,"superseded","WRITE_INTENT_SUPERSEDED",at)
        return self._result(intent.write_intent_id,getattr(updated,"status","not_found"),reason if updated else "intent_not_found",at,checks)

    @staticmethod
    def _result(identifier,status,reason,at,checks):return AdsWriteIntentLifecycleResult(identifier,status,reason,at,tuple(checks))

    def _hard_limits(self,intent):
        try:
            current=Decimal(intent.current_value);proposed=Decimal(intent.proposed_value)
            if not current.is_finite() or not proposed.is_finite() or current<=0 or proposed<=0:return False
            maximum=self.safety.config.max_bid_increase_percent if intent.direction=="increase" else self.safety.config.max_bid_decrease_percent
            consistent=proposed>current if intent.direction=="increase" else proposed<current
            return consistent and self.safety.percentage_within_limit(current,proposed,maximum) and self.safety.config.max_single_action_amount>0 and proposed<=self.safety.config.max_single_action_amount and self.safety.config.max_actions_per_run>=1
        except (DecimalException,ValueError,TypeError):return False
