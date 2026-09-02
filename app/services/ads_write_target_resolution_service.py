"""Resolves metadata-only advertiser targets; contains no Amazon transport."""
from datetime import datetime, timezone
from typing import Protocol

from app.amazon_ads.write_target_models import AdsResolvedAdvertiserTarget, AdsWriteTargetResolution


class AdsAdvertiserTargetResolver(Protocol):
    def resolve_target(self,seller_id,marketplace_id,profile_id,write_intent): ...


class AdsWriteTargetResolutionService:
    def __init__(self,repository,lifecycle_service,target_resolver=None,now=None):
        self.repository=repository;self.lifecycle=lifecycle_service;self.resolver=target_resolver
        self.now=now or (lambda:datetime.now(timezone.utc))

    @staticmethod
    def _check(name,passed):return {"name":name,"passed":bool(passed)}

    def resolve(self,seller,marketplace,profile,write_intent_id,confirm=False):
        profile=str(profile);checks=[];intent=None;target=None
        def stop(status):return AdsWriteTargetResolution.create(write_intent_id,seller,marketplace,profile,status,False,checks,self.now(),intent,target)
        def require(name,passed,status):
            checks.append(self._check(name,passed));return None if passed else stop(status)
        result=require("EXPLICIT_CONFIRMATION",confirm is True,"confirmation_required")
        if result:return result
        intent=self.repository.get_write_intent(seller,marketplace,profile,write_intent_id)
        result=require("INTENT_EXISTS",intent is not None,"intent_not_found")
        if result:return result
        result=require("INTENT_PREPARED",intent.status=="prepared","intent_not_prepared")
        if result:return result
        result=require("SCOPE",intent.seller_id==seller and intent.marketplace_id==marketplace and intent.profile_id==profile,"scope_mismatch")
        if result:return result
        result=require("SUPPORTED_ACTION",intent.action_type=="BID_DIRECTION_REVIEW","unsupported_action")
        if result:return result
        # Ambiguous scopes are rejected before a resolver can influence semantics.
        result=require("SUPPORTED_MUTATION_SCOPE",intent.scope_type=="keyword","unsupported_mutation_scope")
        if result:return result
        result=require("VALID_DIRECTION",intent.direction in ("increase","decrease"),"invalid_direction")
        if result:return result
        before=(intent.status,intent.current_value,intent.proposed_value,intent.scope_type,intent.scope_id,intent.action_type,intent.direction)
        lifecycle=self.lifecycle.revalidate(seller,marketplace,profile,write_intent_id,True)
        current=self.repository.get_write_intent(seller,marketplace,profile,write_intent_id)
        lifecycle_ok=lifecycle.status=="prepared" and lifecycle.reason_code=="current" and current is not None
        result=require("AUTHORITATIVE_REVALIDATION",lifecycle_ok,"intent_not_current")
        if result:return result
        after=(current.status,current.current_value,current.proposed_value,current.scope_type,current.scope_id,current.action_type,current.direction)
        result=require("INTENT_UNCHANGED",before==after,"intent_not_current")
        if result:return result
        intent=current
        result=require("TRUSTED_RESOLVER",self.resolver is not None,"target_resolution_unavailable")
        if result:return result
        try:target=self.resolver.resolve_target(seller,marketplace,profile,intent)
        except Exception:target=None
        result=require("TARGET_FOUND",target is not None,"target_not_found")
        if result:return result
        def required(value):return "" if value is None else str(value).strip()
        try:
            normalized=AdsResolvedAdvertiserTarget(
                required(target.ad_product),required(target.advertiser_entity_type),
                required(target.advertiser_entity_id),required(target.mutation_kind),
                str(target.campaign_id).strip() if target.campaign_id is not None else None,
                str(target.ad_group_id).strip() if target.ad_group_id is not None else None)
        except (AttributeError,TypeError,ValueError):
            target=None
            return stop("target_not_found")
        target=normalized
        for name,passed,status in (
            ("AD_PRODUCT",target.ad_product=="SP","unsupported_ad_product"),
            ("ENTITY_TYPE",target.advertiser_entity_type=="keyword","unsupported_entity_type"),
            ("ENTITY_ID",bool(target.advertiser_entity_id),"invalid_target_identifier"),
            ("ENTITY_SCOPE",target.advertiser_entity_id==intent.scope_id,"target_scope_mismatch"),
            ("CAMPAIGN_ID",target.campaign_id is None or bool(target.campaign_id),"invalid_target_identifier"),
            ("AD_GROUP_ID",target.ad_group_id is None or bool(target.ad_group_id),"invalid_target_identifier"),
            ("MUTATION_KIND",target.mutation_kind=="SP_KEYWORD_BID","unsupported_mutation_kind")):
            result=require(name,passed,status)
            if result:return result
        return AdsWriteTargetResolution.create(write_intent_id,seller,marketplace,profile,"eligible_target_resolution",True,checks,self.now(),intent,target)
