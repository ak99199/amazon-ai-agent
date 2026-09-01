"""Internal validation only; deliberately contains no Amazon transport."""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from app.amazon_ads.write_models import AdsWriteConfig,AdsWritePreflight
from app.services.ads_execution_safety_service import AdsExecutionSafetyService

SUPPORTED_ACTIONS=frozenset({"BID_DIRECTION_REVIEW","NEGATIVE_KEYWORD_REVIEW","KEYWORD_RESEARCH_REVIEW"})
ACTION_CODES={"BID_INCREASE_CANDIDATE":"BID_DIRECTION_REVIEW","BID_DECREASE_CANDIDATE":"BID_DIRECTION_REVIEW","NEGATIVE_KEYWORD_CANDIDATE":"NEGATIVE_KEYWORD_REVIEW","KEYWORD_HARVEST_CANDIDATE":"KEYWORD_RESEARCH_REVIEW"}

class AdsWritePreflightService:
 def __init__(self,recommendation_service,repository,config=None,approval_status="pending",safety_service=None,now=None):self.recommendations=recommendation_service;self.repository=repository;self.config=config or AdsWriteConfig.from_environment();self.approval_status=str(approval_status or "pending").lower();self.safety=safety_service or AdsExecutionSafetyService();self.now=now or (lambda:datetime.now(timezone.utc))
 @staticmethod
 def _check(name,passed,reason):return {"name":name,"passed":bool(passed),"reason":reason}
 def preflight(self,seller,marketplace,profile,execution_plan_id,confirm=False,window=30):
  profile=str(profile);plan=None;checks=[]
  def add(name,passed,reason):checks.append(self._check(name,passed,reason));return passed
  if not add("EXPLICIT_CONFIRMATION",confirm is True,"Explicit controlled-write preflight confirmation is required."):return self._result(execution_plan_id,seller,marketplace,profile,"confirmation_required",False,checks,plan)
  if not add("WRITE_CONFIGURATION",self.config.valid,"Write configuration is valid."):return self._result(execution_plan_id,seller,marketplace,profile,"write_disabled",False,checks,plan)
  if not add("WRITE_FEATURE_ENABLED",self.config.enabled,"Controlled write preflight is enabled."):return self._result(execution_plan_id,seller,marketplace,profile,"write_disabled",False,checks,plan)
  if not add("WRITE_DRY_RUN_ONLY",self.config.dry_run_only,"Dry-run-only write preparation is enforced."):return self._result(execution_plan_id,seller,marketplace,profile,"dry_run_only",False,checks,plan)
  if not add("ADS_APPROVAL",self.approval_status=="approved","Amazon Ads approval is approved."):return self._result(execution_plan_id,seller,marketplace,profile,"approval_pending",False,checks,plan)
  plans=self.repository.list_execution_plans(seller,marketplace,profile,200);plan=next((item for item in plans if item.stable_execution_plan_id==execution_plan_id),None)
  if not add("CURRENT_EXECUTION_PLAN",bool(plan),"Execution plan exists in the authoritative scope."):return self._result(execution_plan_id,seller,marketplace,profile,"plan_not_found",False,checks,None)
  decision=self.repository.get_decision(seller,marketplace,profile,plan.recommendation_id)
  if not add("APPROVED_DECISION",bool(decision and decision.status=="approved" and decision.stable_decision_id==plan.decision_id),"Stored decision remains approved."):return self._result(execution_plan_id,seller,marketplace,profile,"decision_not_approved",False,checks,plan)
  if not add("PLAN_ELIGIBLE",plan.eligible is True,"Execution plan remains eligible."):return self._result(execution_plan_id,seller,marketplace,profile,"plan_not_eligible",False,checks,plan)
  if not add("PLAN_DRY_RUN",plan.dry_run is True,"Execution plan is dry-run only."):return self._result(execution_plan_id,seller,marketplace,profile,"plan_not_eligible",False,checks,plan)
  scope=plan.seller_id==seller and plan.marketplace_id==marketplace and str(plan.profile_id)==profile
  add("SELLER_MATCH",plan.seller_id==seller,"Seller scope matches.");add("MARKETPLACE_MATCH",plan.marketplace_id==marketplace,"Marketplace scope matches.");add("PROFILE_MATCH",str(plan.profile_id)==profile,"Profile scope matches.")
  if not scope:return self._result(execution_plan_id,seller,marketplace,profile,"scope_mismatch",False,checks,plan)
  current=next((item for item in self.recommendations.get_recommendations(seller,marketplace,profile,window) if item.recommendation_id==plan.recommendation_id),None)
  current_ok=bool(current and current.recommendation_code==plan.recommendation_code and current.scope_type==plan.scope_type and current.scope_id==plan.scope_id)
  if not add("CURRENT_RECOMMENDATION",current_ok,"Recommendation remains current and unchanged."):return self._result(execution_plan_id,seller,marketplace,profile,"stale_recommendation",False,checks,plan)
  supported=plan.action_type in SUPPORTED_ACTIONS and ACTION_CODES.get(plan.recommendation_code)==plan.action_type
  if not add("SUPPORTED_ACTION",supported,"Action is in the controlled future-write allowlist."):return self._result(execution_plan_id,seller,marketplace,profile,"unsupported_action",False,checks,plan)
  exact=plan.current_value is not None and plan.proposed_value is not None
  if not add("EXACT_VALUE_AVAILABLE",exact,"Validated exact current and proposed values are present."):return self._result(execution_plan_id,seller,marketplace,profile,"exact_value_required",False,checks,plan)
  hard=self._hard_limits(plan)
  if not add("HARD_LIMITS",hard,"Exact values remain within configured hard limits."):return self._result(execution_plan_id,seller,marketplace,profile,"hard_limit_violation",False,checks,plan)
  return self._result(execution_plan_id,seller,marketplace,profile,"eligible_preflight",True,checks,plan)
 def _hard_limits(self,plan):
  if plan.action_type!="BID_DIRECTION_REVIEW":return True
  try:
   current=Decimal(plan.current_value);proposed=Decimal(plan.proposed_value)
   if not current.is_finite() or not proposed.is_finite() or current<=0 or proposed<0:return False
   maximum=self.safety.config.max_bid_increase_percent if plan.direction=="increase" else self.safety.config.max_bid_decrease_percent
   return self.safety.percentage_within_limit(current,proposed,maximum) and self.safety.config.max_single_action_amount>0 and proposed<=self.safety.config.max_single_action_amount and self.safety.config.max_actions_per_run>=1
  except (InvalidOperation,ValueError,TypeError):return False
 def _result(self,plan_id,seller,marketplace,profile,status,eligible,checks,plan):return AdsWritePreflight.create(plan_id,seller,marketplace,profile,status,eligible,checks,self.now(),plan)
