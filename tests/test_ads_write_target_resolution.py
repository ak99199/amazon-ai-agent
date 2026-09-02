from dataclasses import replace
from datetime import datetime,timezone
from types import SimpleNamespace

from app.amazon_ads.write_target_models import AdsResolvedAdvertiserTarget
from app.services.ads_write_target_resolution_service import AdsWriteTargetResolutionService
from tests.test_ads_write_intent_revalidation import setup

NOW=datetime(2026,2,14,tzinfo=timezone.utc)

class Repo:
 def __init__(self,intent):self.intent=intent
 def get_write_intent(self,s,m,p,i):return self.intent if self.intent and (self.intent.seller_id,self.intent.marketplace_id,self.intent.profile_id,self.intent.write_intent_id)==(s,m,str(p),i) else None
class Lifecycle:
 def __init__(self,status="prepared",reason="current"):self.status=status;self.reason=reason
 def revalidate(self,*args):return SimpleNamespace(status=self.status,reason_code=self.reason)
class Resolver:
 def __init__(self,target=None,error=False):self.target=target;self.error=error;self.calls=[]
 def resolve_target(self,*args):
  self.calls.append(args)
  if self.error:raise RuntimeError("safe fake failure")
  return self.target
def fixtures(scope="keyword",action="BID_DIRECTION_REVIEW",direction="increase",status="prepared"):
 _,repo,*_=setup();intent=replace(repo.intent,scope_type=scope,scope_id="keyword-1",action_type=action,direction=direction,status=status)
 target=AdsResolvedAdvertiserTarget("SP","keyword","keyword-1","SP_KEYWORD_BID"," campaign-1 "," ad-group-1 ")
 resolver=Resolver(target);service=AdsWriteTargetResolutionService(Repo(intent),Lifecycle(),resolver,lambda:NOW)
 return service,resolver,intent,target

def test_confirmation_missing_and_terminal_intents_block():
 service,_,intent,_=fixtures();assert service.resolve("s","m","p",intent.write_intent_id).status=="confirmation_required"
 assert service.resolve("other","m","p",intent.write_intent_id,True).status=="intent_not_found"
 for status in ("cancelled","superseded"):
  service,_,intent,_=fixtures(status=status);assert service.resolve("s","m","p",intent.write_intent_id,True).status=="intent_not_prepared"

def test_authoritative_revalidation_must_be_current():
 service,_,intent,_=fixtures();service.lifecycle=Lifecycle("superseded","stale_recommendation")
 assert service.resolve("s","m","p",intent.write_intent_id,True).status=="intent_not_current"

def test_campaign_and_search_term_are_blocked_before_resolver():
 for scope in ("campaign","search_term"):
  service,resolver,intent,_=fixtures(scope=scope);result=service.resolve("s","m","p",intent.write_intent_id,True)
  assert result.status=="unsupported_mutation_scope" and resolver.calls==[]

def test_unsupported_action_direction_and_missing_resolver_block():
 service,_,intent,_=fixtures(action="KEYWORD_RESEARCH_REVIEW");assert service.resolve("s","m","p",intent.write_intent_id,True).status=="unsupported_action"
 service,_,intent,_=fixtures(direction="none");assert service.resolve("s","m","p",intent.write_intent_id,True).status=="invalid_direction"
 service,_,intent,_=fixtures();service.resolver=None;assert service.resolve("s","m","p",intent.write_intent_id,True).status=="target_resolution_unavailable"

def test_valid_keyword_target_is_normalized_safe_and_deterministic():
 service,resolver,intent,_=fixtures();first=service.resolve("s","m","p",intent.write_intent_id,True);second=service.resolve("s","m","p",intent.write_intent_id,True)
 assert first.eligible and first.status=="eligible_target_resolution" and first.target_resolution_id==second.target_resolution_id
 assert first.campaign_id=="campaign-1" and first.ad_group_id=="ad-group-1"
 public=first.public_dict();assert all(x not in str(public).lower() for x in ("authorization","access_token","refresh_token","endpoint","http_method"))
 assert not hasattr(AdsWriteTargetResolutionService,"execute") and not hasattr(AdsWriteTargetResolutionService,"apply")

def test_target_provider_failures_and_mismatches_fail_closed():
 service,resolver,intent,target=fixtures();resolver.error=True;assert service.resolve("s","m","p",intent.write_intent_id,True).status=="target_not_found"
 changes=(("ad_product","SB","unsupported_ad_product"),("advertiser_entity_type","target","unsupported_entity_type"),("advertiser_entity_id","","invalid_target_identifier"),("advertiser_entity_id","other","target_scope_mismatch"),("mutation_kind","OTHER","unsupported_mutation_kind"),("campaign_id"," ","invalid_target_identifier"),("ad_group_id"," ","invalid_target_identifier"))
 for field,value,status in changes:
  service,resolver,intent,target=fixtures();resolver.target=replace(target,**{field:value});assert service.resolve("s","m","p",intent.write_intent_id,True).status==status
