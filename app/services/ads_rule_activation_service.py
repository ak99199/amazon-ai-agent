"""Explicit, human-controlled activation of internal recommendation rules only."""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from uuid import uuid4
from app.amazon_ads.rule_activation_models import AdsRuleActivationCheck,AdsRuleActivationRequest,AdsRuleActivationResult
from app.amazon_ads.rule_tuning_models import ALLOWED_TUNING_PARAMETERS,MAX_RELATIVE_TUNING_CHANGE,relative_change_percent,validate_threshold_snapshot

class AdsRuleActivationService:
 def __init__(self,repository,resolver=None,now=None,id_factory=None):self.repository=repository;self.resolver=resolver;self.now=now or (lambda:datetime.now(timezone.utc));self.id_factory=id_factory or (lambda:str(uuid4()))
 def activate(self,request=None,**kwargs):
  if request is None:request=AdsRuleActivationRequest(**kwargs)
  elif not isinstance(request,AdsRuleActivationRequest):raise TypeError("request must be AdsRuleActivationRequest")
  checks=[]
  def add(code,passed,yes,no):checks.append(AdsRuleActivationCheck(code,bool(passed),yes if passed else no));return bool(passed)
  scope=(request.seller_id,request.marketplace_id,str(request.profile_id));target=self.repository.get_rule_version(*scope,request.target_rule_version_id)
  add("VERSION_EXISTS",target is not None,"Target rule version exists.","Target rule version was not found in this scope.");add("SCOPE_MATCH",target is not None,"Target rule version matches the requested scope.","Target rule version scope does not match.")
  if target and target["status"]=="active":
   add("NOT_ALREADY_ACTIVE",False,"Target is not active.","Target rule version is already active.");return self._result("already_active",request,checks,target["rule_version_id"],target.get("activated_at"))
  add("NOT_ALREADY_ACTIVE",True,"Target is not already active.","Target rule version is already active.");add("STATUS_PROPOSED",bool(target and target["status"]=="proposed"),"Target status is proposed.","Only a proposed rule version can be activated.");add("EXPLICIT_CONFIRMATION",request.confirm is True,"Explicit confirmation was supplied.","Explicit confirmation is required.")
  proposal=None;source_id=target.get("source_proposal_id") if target else None;requires=bool(target and (source_id or target.get("source") in ("tuning_proposal","rule_tuning_proposal")))
  if requires and source_id:proposal=self.repository.get_rule_tuning_proposal(*scope,source_id)
  add("SOURCE_PROPOSAL_VALID",not requires or proposal is not None,"Source proposal is valid or not required for this safe source.","The source tuning proposal was not found in this scope.");add("PROPOSAL_APPROVED",not requires or bool(proposal and proposal["status"]=="approved_for_future_rule_version"),"Stored proposal approval is valid or not required.","Stored proposal is not approved for a future rule version.")
  checks.extend(self._validate_thresholds(target,proposal));current=self.repository.get_active_rule_version(*scope);current_id=current["rule_version_id"] if current else None;expected_ok=current_id==request.expected_active_rule_version_id;add("EXPECTED_ACTIVE_MATCH",expected_ok,"Expected active rule version matches.","Active rule version changed; activation was not applied.")
  if not all(item.passed for item in checks):return self._result("conflict" if not expected_ok else "blocked",request,checks,current_id,None)
  event_id=self.id_factory();activated_at=self.now()
  try:changed=self.repository.activate_rule_version(*scope,request.target_rule_version_id,request.expected_active_rule_version_id,event_id,activated_at)
  except Exception:return self._result("error",request,checks,current_id,None)
  if changed is None:checks.append(AdsRuleActivationCheck("EXPECTED_ACTIVE_MATCH",False,"Active rule version changed inside the activation transaction."));return self._result("conflict",request,checks,current_id,None)
  return AdsRuleActivationResult("activated",event_id,*scope,changed["previous_rule_version_id"],request.target_rule_version_id,tuple(checks),activated_at)
 def _validate_thresholds(self,target,proposal):
  parsed,well,white,bounds=validate_threshold_snapshot(target.get("thresholds") if target else None);maximum=True
  if proposal:
   parameter=proposal.get("parameter_name");maximum=parameter in ALLOWED_TUNING_PARAMETERS and parameter in parsed
   if maximum:
    try:maximum=relative_change_percent(proposal["current_value"],parsed[parameter])<=MAX_RELATIVE_TUNING_CHANGE and parsed[parameter]==Decimal(str(proposal["proposed_value"]))
    except (InvalidOperation,ValueError,TypeError):maximum=False
  return [AdsRuleActivationCheck("THRESHOLDS_VALID",well,"Threshold snapshot is Decimal-safe." if well else "Threshold snapshot is malformed."),AdsRuleActivationCheck("PARAMETERS_WHITELISTED",white,"All parameters are whitelisted." if white else "Threshold snapshot contains an unknown parameter."),AdsRuleActivationCheck("SAFETY_BOUNDS_VALID",bounds,"Thresholds satisfy safety bounds." if bounds else "A threshold violates safety bounds."),AdsRuleActivationCheck("MAX_CHANGE_VALID",maximum,"Proposal change satisfies the shared maximum-change policy." if maximum else "Proposal change exceeds or disagrees with the approved value.")]
 @staticmethod
 def _result(status,request,checks,active_id,activated_at):
  if isinstance(activated_at,str):activated_at=datetime.fromisoformat(activated_at)
  return AdsRuleActivationResult(status,None,request.seller_id,request.marketplace_id,str(request.profile_id),None,active_id,tuple(checks),activated_at)
