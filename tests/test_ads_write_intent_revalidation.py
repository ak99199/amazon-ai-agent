from dataclasses import replace
from datetime import datetime, timezone

from app.amazon_ads.write_models import AdsWriteConfig
from app.services.ads_write_intent_revalidation_service import AdsWriteIntentRevalidationService
from tests.test_ads_write_intent_service import trusted
from tests.test_ads_exact_value_proposal_service import safety
from tests.test_ads_write_preflight_service import Recommendations

NOW=datetime(2026,2,13,tzinfo=timezone.utc)

class Repo:
 def __init__(self,intent,plan,decision):self.intent=intent;self.plan=plan;self.decision=decision;self.events=[]
 def get_write_intent(self,s,m,p,i):return self.intent if self.intent and (self.intent.seller_id,self.intent.marketplace_id,self.intent.profile_id,self.intent.write_intent_id)==(s,m,str(p),i) else None
 def list_execution_plans(self,*args):return [] if self.plan is None else [self.plan]
 def get_decision(self,*args):return self.decision
 def transition_write_intent(self,s,m,p,i,status,event,at):
  if self.intent.status=="prepared":
   self.intent=replace(self.intent,status=status);self.events.append((i,event))
  return self.intent

def setup():
 maker,_,current,decision,plan,proposal,preflight=trusted();intent=maker.prepare("s","m","p","plan",True,proposal,preflight)
 repo=Repo(intent,plan,decision)
 service=AdsWriteIntentRevalidationService(Recommendations(current),repo,lambda i:proposal,lambda i:preflight,AdsWriteConfig(True,True,True),"approved",safety(),lambda:NOW)
 return service,repo,current,decision,plan,proposal,preflight

def test_matching_intent_stays_prepared_and_output_is_safe():
 service,repo,*_=setup();result=service.revalidate("s","m","p",repo.intent.write_intent_id,True)
 assert result.status=="prepared" and result.reason_code=="current" and repo.events==[]
 assert "secret" not in str(result.public_dict()).lower()

def test_missing_nonprepared_and_scope_isolation():
 service,repo,*_=setup();identifier=repo.intent.write_intent_id
 assert service.revalidate("other","m","p",identifier,True).reason_code=="intent_not_found"
 repo.intent=replace(repo.intent,status="cancelled")
 assert service.revalidate("s","m","p",identifier,True).reason_code=="intent_not_prepared"

def test_configuration_plan_decision_and_recommendation_drift_supersede_once():
 for change,reason in (("write","write_disabled"),("plan","plan_missing"),("decision","decision_not_approved"),("recommendation","stale_recommendation")):
  service,repo,*_=setup()
  if change=="write":service.write_config=AdsWriteConfig(False,True,True)
  if change=="plan":repo.plan=None
  if change=="decision":repo.decision=replace(repo.decision,status="rejected")
  if change=="recommendation":service.recommendations.current=None
  first=service.revalidate("s","m","p",repo.intent.write_intent_id,True)
  second=service.revalidate("s","m","p",repo.intent.write_intent_id,True)
  assert first.status=="superseded" and first.reason_code==reason
  assert second.reason_code=="intent_not_prepared" and len(repo.events)==1

def test_proposal_preflight_values_direction_and_limits_supersede():
 cases=(("proposal","proposal_mismatch"),("preflight","preflight_mismatch"),("current","current_value_changed"),("proposed","proposed_value_changed"),("direction","invalid_direction"),("limits","hard_limit_violation"))
 for change,reason in cases:
  service,repo,current,decision,plan,proposal,preflight=setup()
  if change=="proposal":service.proposal_resolver=lambda i:replace(proposal,proposal_id="other")
  if change=="preflight":service.preflight_resolver=lambda i:replace(preflight,preflight_id="other")
  if change=="current":service.proposal_resolver=lambda i:replace(proposal,current_value="2")
  if change=="proposed":service.proposal_resolver=lambda i:replace(proposal,proposed_value="2")
  if change=="direction":repo.plan=replace(plan,direction="decrease")
  if change=="limits":service.safety=safety(amount=0)
  result=service.revalidate("s","m","p",repo.intent.write_intent_id,True)
  assert result.status=="superseded" and result.reason_code==reason

def test_cancellation_confirmation_idempotency_and_no_resurrection():
 service,repo,*_=setup();identifier=repo.intent.write_intent_id
 assert service.cancel("s","m","p",identifier,False).reason_code=="confirmation_required"
 first=service.cancel("s","m","p",identifier,True);second=service.cancel("s","m","p",identifier,True)
 assert first.status=="cancelled" and second.reason_code=="intent_not_prepared" and len(repo.events)==1
 assert not hasattr(AdsWriteIntentRevalidationService,"execute") and not hasattr(AdsWriteIntentRevalidationService,"apply")
