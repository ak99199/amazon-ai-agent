"""Explicit, history-driven rollback of internal recommendation rules only."""
from datetime import datetime,timezone
from uuid import uuid4
from app.amazon_ads.rule_activation_models import AdsRuleActivationCheck,AdsRuleRollbackRequest,AdsRuleRollbackResult,AdsRuleRollbackStatus
from app.amazon_ads.rule_tuning_models import validate_threshold_snapshot

class AdsRuleRollbackService:
 def __init__(self,repository,now=None,id_factory=None):self.repository=repository;self.now=now or (lambda:datetime.now(timezone.utc));self.id_factory=id_factory or (lambda:str(uuid4()))
 def get_rollback_status(self,seller_id,marketplace_id,profile_id):
  current=self.repository.get_active_rule_version(seller_id,marketplace_id,str(profile_id));candidate=self.repository.get_rollback_candidate(seller_id,marketplace_id,str(profile_id),current["rule_version_id"] if current else None) if current else None
  valid=bool(candidate and candidate["status"]=="archived" and all(validate_threshold_snapshot(candidate["thresholds"])[1:]))
  return AdsRuleRollbackStatus(valid,current["rule_version_id"] if current else None,candidate["rule_version_id"] if valid else None)
 def rollback(self,request=None,**kwargs):
  if request is None:request=AdsRuleRollbackRequest(**kwargs)
  elif not isinstance(request,AdsRuleRollbackRequest):raise TypeError("request must be AdsRuleRollbackRequest")
  scope=(request.seller_id,request.marketplace_id,str(request.profile_id));checks=[]
  def add(code,passed,yes,no):checks.append(AdsRuleActivationCheck(code,bool(passed),yes if passed else no))
  current=self.repository.get_active_rule_version(*scope);current_id=current["rule_version_id"] if current else None
  add("CURRENT_ACTIVE_EXISTS",current is not None,"Current active version exists.","No active rule version exists.")
  expected=current_id==request.expected_active_rule_version_id;add("EXPECTED_ACTIVE_MATCH",expected,"Expected active rule version matches.","Active rule version changed; rollback was not applied.")
  add("EXPLICIT_CONFIRMATION",request.confirm is True,"Explicit confirmation was supplied.","Explicit confirmation is required.")
  candidate=self.repository.get_rollback_candidate(*scope,current_id) if current else None
  add("ROLLBACK_HISTORY_EXISTS",candidate is not None,"Activation predecessor was found.","No activation predecessor exists.")
  parsed,well,white,bounds=validate_threshold_snapshot(candidate.get("thresholds") if candidate else None)
  add("PREVIOUS_VERSION_VALID",bool(candidate and candidate["status"]=="archived"),"Previous version is restorable.","Previous version is missing, rejected, or not archived.");add("THRESHOLDS_VALID",well,"Previous threshold snapshot is Decimal-safe.","Previous threshold snapshot is malformed.");add("PARAMETERS_WHITELISTED",white,"Previous parameters are whitelisted.","Previous snapshot contains an unknown parameter.");add("SAFETY_BOUNDS_VALID",bounds,"Previous thresholds satisfy safety bounds.","A previous threshold violates safety bounds.")
  if not expected:return self._result("conflict",request,checks,current_id,None)
  if not request.confirm:return self._result("blocked",request,checks,current_id,None)
  if current and candidate is None:return self._result("no_history",request,checks,current_id,None)
  if not current or not all(item.passed for item in checks):return self._result("blocked",request,checks,current_id,None)
  rollback_id=self.id_factory();rolled_back_at=self.now()
  try:outcome=self.repository.rollback_rule_version(*scope,request.expected_active_rule_version_id,rollback_id,rolled_back_at)
  except Exception:return self._result("error",request,checks,current_id,None)
  if outcome["status"]!="rolled_back":return self._result(outcome["status"],request,checks,current_id,None)
  return AdsRuleRollbackResult("rolled_back",rollback_id,*scope,current_id,outcome["to_rule_version_id"],tuple(checks),rolled_back_at)
 @staticmethod
 def _result(status,request,checks,current_id,restored_id):return AdsRuleRollbackResult(status,None,request.seller_id,request.marketplace_id,str(request.profile_id),current_id,restored_id,tuple(checks),None)
