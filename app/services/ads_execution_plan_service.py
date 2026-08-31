"""Builds validated, persisted dry-run plans without any Amazon network call."""
from datetime import datetime, timezone
from app.amazon_ads.execution_models import AdsExecutionPlan
from app.services.ads_execution_safety_service import AdsExecutionSafetyService


class UnknownAdsExecutionRecommendationError(LookupError): pass


_ACTIONS = {
    "BID_INCREASE_CANDIDATE": ("BID_DIRECTION_REVIEW", "increase"),
    "BID_DECREASE_CANDIDATE": ("BID_DIRECTION_REVIEW", "decrease"),
    "NEGATIVE_KEYWORD_CANDIDATE": ("NEGATIVE_KEYWORD_REVIEW", "none"),
    "KEYWORD_HARVEST_CANDIDATE": ("KEYWORD_RESEARCH_REVIEW", "none"),
}


class AdsExecutionPlanService:
    """Plans only. This class has no executor and never makes HTTP requests."""
    def __init__(self, recommendation_service, repository, safety_service=None, now=None):
        self.recommendation_service=recommendation_service; self.repository=repository
        self.safety_service=safety_service or AdsExecutionSafetyService(); self.now=now or (lambda:datetime.now(timezone.utc))

    def list_plans(self,seller_id,marketplace_id,profile_id,limit=50):
        return [plan.public_dict() for plan in self.repository.list_execution_plans(seller_id,marketplace_id,profile_id,limit)]

    def create_dry_run(self,seller_id,marketplace_id,profile_id,recommendation_id,window=30):
        decision=self.repository.get_decision(seller_id,marketplace_id,profile_id,recommendation_id)
        current=next((item for item in self.recommendation_service.get_recommendations(seller_id,marketplace_id,profile_id,window) if item.recommendation_id==recommendation_id),None)
        if not decision and not current: raise UnknownAdsExecutionRecommendationError("Ads recommendation is not available")
        context=current or decision
        action_type,direction=_ACTIONS.get(context.recommendation_code,("UNSUPPORTED_REVIEW","none"))
        checks=[]
        checks.append(self.safety_service.check("APPROVED",bool(decision and decision.status=="approved"),"Stored decision is approved." if decision and decision.status=="approved" else "A stored approved decision is required."))
        checks.append(self.safety_service.check("CURRENT_RECOMMENDATION",bool(current),"Recommendation is current." if current else "Recommendation is stale."))
        checks.append(self.safety_service.check("SELLER_MATCH",bool(decision and decision.seller_id==seller_id),"Seller scope matches." if decision and decision.seller_id==seller_id else "Seller scope does not match."))
        checks.append(self.safety_service.check("MARKETPLACE_MATCH",bool(decision and decision.marketplace_id==marketplace_id),"Marketplace scope matches." if decision and decision.marketplace_id==marketplace_id else "Marketplace scope does not match."))
        checks.append(self.safety_service.check("PROFILE_MATCH",bool(decision and decision.profile_id==str(profile_id)),"Profile scope matches." if decision and decision.profile_id==str(profile_id) else "Profile scope does not match."))
        checks.append(self.safety_service.check("SUPPORTED_ACTION",action_type!="UNSUPPORTED_REVIEW","Supported review action." if action_type!="UNSUPPORTED_REVIEW" else "Recommendation does not map to a controlled future action."))
        prototype=AdsExecutionPlan(recommendation_id,decision.stable_decision_id if decision else None,seller_id,marketplace_id,str(profile_id),context.scope_type,context.scope_id,context.recommendation_code,action_type,direction)
        existing=self.repository.get_execution_plan(seller_id,marketplace_id,profile_id,prototype.plan_hash)
        checks.append(self.safety_service.check("NOT_DUPLICATE",True,"Existing identical plan is returned idempotently." if existing else "No identical plan exists."))
        checks.append(self.safety_service.check("WITHIN_HARD_LIMITS",True,"No exact monetary value is prepared; no amount is invented."))
        checks.append(self.safety_service.check("DRY_RUN_ONLY",True,"This plan is always a dry run; no Amazon request is sent."))
        checks.append(self.safety_service.configuration_check())
        eligible=all(item["passed"] for item in checks)
        failed=next((item for item in checks if not item["passed"]),None)
        code="eligible_dry_run" if eligible else self._status_for(failed["name"])
        plan=AdsExecutionPlan(recommendation_id,decision.stable_decision_id if decision else None,seller_id,marketplace_id,str(profile_id),context.scope_type,context.scope_id,context.recommendation_code,action_type,direction,None,None,True,eligible,code,code,failed["reason"] if failed else "All mandatory dry-run safety checks passed.",tuple(checks),self.now())
        return self.repository.save_execution_plan(plan)

    @staticmethod
    def _status_for(name):
        return {"APPROVED":"not_approved","CURRENT_RECOMMENDATION":"stale_recommendation","SUPPORTED_ACTION":"unsupported_action","SELLER_MATCH":"scope_mismatch","MARKETPLACE_MATCH":"scope_mismatch","PROFILE_MATCH":"scope_mismatch","CONFIG_SAFE":"configuration_blocked","WITHIN_HARD_LIMITS":"hard_limit_violation"}.get(name,"error")

