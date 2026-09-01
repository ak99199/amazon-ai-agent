"""Bounded, read-only structural validation of Sponsored Products targeting."""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from app.amazon_ads.auth import AdsAuthenticationError
from app.amazon_ads.campaigns import SponsoredProductsCampaignsService
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.keywords import SponsoredProductsKeywordsService
from app.amazon_ads.live_models import AdsLiveTargetingValidationResult
from app.services.ads_live_entity_validation_service import AdsLiveEntityValidationService

class AdsLiveTargetingValidationService:
 def __init__(self,readiness_service,dependency_factory,now=None):self.readiness_service=readiness_service;self.dependency_factory=dependency_factory;self.now=now or (lambda:datetime.now(timezone.utc))
 def run(self,confirm_live_read=False):
  started=self.now();ready=self.readiness_service.get();profile={"configured":ready.profile_id_present,"discovered":0,"matched":False};empty=self._counts();relationships={"valid":0,"invalid":0,"unresolved":0,"bounded":True}
  if confirm_live_read is not True:return self._result("blocked_confirmation",started,ready,profile,empty,empty,empty,empty,relationships,(),ready.blocking_reasons)
  if not ready.manual_smoke_test_allowed:return self._result("blocked_readiness",started,ready,profile,empty,empty,empty,empty,relationships,(),ready.blocking_reasons)
  try:profiles_service,adapter=self.dependency_factory()
  except Exception:return self._result("remote_error",started,ready,profile,empty,empty,empty,empty,relationships,(),())
  try:profiles=profiles_service.list_profiles()
  except (AdsAuthenticationError,AdsApiClientError) as error:return self._error(error,started,ready,profile,empty,empty,empty,empty,relationships)
  except Exception:return self._result("profile_discovery_error",started,ready,profile,empty,empty,empty,empty,relationships,(),())
  configured=str(self.readiness_service.settings.profile_id);matched=next((item for item in profiles if str(item.profile_id)==configured),None);profile={"configured":True,"discovered":len(profiles),"matched":bool(matched),"country_code":getattr(matched,"country_code",None),"currency_code":getattr(matched,"currency_code",None)}
  if not matched:return self._result("profile_not_found",started,ready,profile,empty,empty,empty,empty,relationships,(),())
  warnings=()
  try:
   campaign_rows=adapter.first_campaign_page(configured,10);ad_group_rows=adapter.first_ad_group_page(configured,20);keyword_rows=adapter.first_keyword_page(configured,25);target_rows=adapter.first_target_page(configured,25)
  except (AdsAuthenticationError,AdsApiClientError) as error:return self._error(error,started,ready,profile,empty,empty,empty,empty,relationships)
  except Exception:return self._result("remote_error",started,ready,profile,empty,empty,empty,empty,relationships,warnings,())
  if any(rows is None for rows in (campaign_rows,ad_group_rows,keyword_rows,target_rows)):return self._result("validation_error",started,ready,profile,empty,empty,empty,empty,relationships,warnings,())
  campaign_rows=self._canonical_rows(campaign_rows,"campaign");ad_group_rows=self._canonical_rows(ad_group_rows,"ad_group");keyword_rows=self._canonical_rows(keyword_rows,"keyword");target_rows=self._canonical_rows(target_rows,"target")
  campaign_counts,campaigns=self._validate_rows(campaign_rows,lambda row:SponsoredProductsCampaignsService._normalize(configured,row),self._campaign)
  ad_group_counts,ad_groups=self._validate_rows(ad_group_rows,adapter._ad_group,self._ad_group)
  keyword_counts,keywords=self._validate_rows(keyword_rows,lambda row:SponsoredProductsKeywordsService._normalize(configured,row,"keyword"),self._keyword)
  target_counts,targets=self._validate_rows(target_rows,adapter._target,self._target)
  relationships=self._relationships(campaigns,ad_groups,keywords,targets)
  received=sum(item["records_received"] for item in (campaign_counts,ad_group_counts,keyword_counts,target_counts));invalid=sum(item["records_invalid"]+item["duplicate_count"] for item in (campaign_counts,ad_group_counts,keyword_counts,target_counts))
  status="valid_empty" if received==0 else "partial_valid" if invalid or relationships["invalid"] or relationships["unresolved"] else "success"
  return self._result(status,started,ready,profile,campaign_counts,ad_group_counts,keyword_counts,target_counts,relationships,warnings,())
 @staticmethod
 def _counts():return {"records_received":0,"records_valid":0,"records_invalid":0,"duplicate_count":0,"bounded":True}
 @classmethod
 def _canonical_rows(cls,rows,kind):return [cls._canonical(row,kind) if isinstance(row,dict) else row for row in rows]
 @staticmethod
 def _canonical(row,kind):
  mappings={
   "campaign":(("campaignId","campaign_id"),),
   "ad_group":(("adGroupId","ad_group_id"),("campaignId","campaign_id"),("defaultBid","default_bid")),
   "keyword":(("keywordId","keyword_id"),("campaignId","campaign_id"),("adGroupId","ad_group_id"),("keywordText","keyword_text"),("matchType","match_type")),
   "target":(("targetId","target_id"),("campaignId","campaign_id"),("adGroupId","ad_group_id")),
  }
  canonical=dict(row)
  for amazon_name,normalized_name in mappings[kind]:
   if amazon_name not in canonical and normalized_name in row:canonical[amazon_name]=row[normalized_name]
  return canonical
 def _validate_rows(self,rows,normalize,validate):
  valid=[];invalid=duplicates=0;seen=set()
  for row in rows:
   if not isinstance(row,dict):invalid+=1;continue
   try:
    item=normalize(row);identifier=validate(row,item)
    if identifier in seen:duplicates+=1;continue
    seen.add(identifier);valid.append(item)
   except (KeyError,ValueError,TypeError,InvalidOperation):invalid+=1
  return {"records_received":len(rows),"records_valid":len(valid),"records_invalid":invalid,"duplicate_count":duplicates,"bounded":True},valid
 @staticmethod
 def _campaign(row,item):AdsLiveEntityValidationService._validate_campaign(row,item);return item.campaign_id
 @staticmethod
 def _ad_group(row,item):
  if not item.ad_group_id or not item.campaign_id:raise ValueError("invalid ad group")
  AdsLiveTargetingValidationService._state_bid(row,item.state,"defaultBid");return item.ad_group_id
 @staticmethod
 def _keyword(row,item):
  if not item.keyword_id or not item.ad_group_id:raise ValueError("invalid keyword")
  if item.match_type is not None and str(item.match_type).lower() not in ("broad","phrase","exact","negativebroad","negativephrase","negativeexact"):raise ValueError("invalid match type")
  AdsLiveTargetingValidationService._state_bid(row,item.state,"bid");return item.keyword_id
 @staticmethod
 def _target(row,item):
  if not item.target_id or not item.ad_group_id:raise ValueError("invalid target")
  expression=row["expression"] if "expression" in row else row.get("targetExpression")
  if expression is not None and (not isinstance(expression,(str,list,dict)) or len(expression)==0):raise ValueError("invalid expression")
  AdsLiveTargetingValidationService._state_bid(row,item.state,"bid");return item.target_id
 @staticmethod
 def _state_bid(row,state,bid_name):
  if state is not None and str(state).lower() not in ("enabled","paused","archived"):raise ValueError("invalid state")
  if row.get(bid_name) is not None:
   bid=Decimal(str(row[bid_name]));
   if not bid.is_finite() or bid<0:raise ValueError("invalid bid")
 @staticmethod
 def _relationships(campaigns,ad_groups,keywords,targets):
  campaign_ids={item.campaign_id for item in campaigns};groups={item.ad_group_id:item for item in ad_groups};valid=invalid=unresolved=0
  for group in ad_groups:
   if group.campaign_id in campaign_ids:valid+=1
   else:unresolved+=1
  for child in (*keywords,*targets):
   parent=groups.get(child.ad_group_id)
   if parent is None:unresolved+=1
   elif child.campaign_id is not None and child.campaign_id!=parent.campaign_id:invalid+=1
   else:valid+=1
  return {"valid":valid,"invalid":invalid,"unresolved":unresolved,"bounded":True}
 @staticmethod
 def _api_status(error):return "auth_error" if isinstance(error,AdsAuthenticationError) or error.status_code in (401,403) else "rate_limited" if error.status_code==429 else "remote_error"
 def _error(self,error,started,ready,profile,campaigns,groups,keywords,targets,relationships):return self._result(self._api_status(error),started,ready,profile,campaigns,groups,keywords,targets,relationships,(),())
 def _result(self,status,started,ready,profile,campaigns,groups,keywords,targets,relationships,warnings,blocking):return AdsLiveTargetingValidationResult(status,started,self.now(),"ready" if ready.manual_smoke_test_allowed else "blocked",profile,campaigns,groups,keywords,targets,relationships,tuple(warnings),tuple(blocking))
