"""Seals internal command metadata only; no payload, dispatcher, or transport."""
from decimal import Decimal,DecimalException
from datetime import datetime,timezone
from app.amazon_ads.write_command_models import AdsSealedWriteCommand,AdsSealedWriteCommandBlockedError,canonical_decimal
from app.amazon_ads.write_models import AdsWriteConfig
from app.services.ads_execution_safety_service import AdsExecutionSafetyService


class AdsSealedWriteCommandService:
 def __init__(self,repository,lifecycle_service,write_config=None,safety_service=None,now=None):
  self.repository=repository;self.lifecycle=lifecycle_service;self.write_config=write_config or AdsWriteConfig.from_environment();self.safety=safety_service or AdsExecutionSafetyService();self.now=now or (lambda:datetime.now(timezone.utc))
 @staticmethod
 def _block(status):raise AdsSealedWriteCommandBlockedError(status)
 def seal(self,seller,marketplace,profile,write_intent_id,confirm=False,target_resolution=None):
  profile=str(profile)
  if confirm is not True:self._block("confirmation_required")
  if not self.write_config.valid or not self.write_config.enabled:self._block("write_disabled")
  if not self.write_config.dry_run_only:self._block("dry_run_only_required")
  intent=self.repository.get_write_intent(seller,marketplace,profile,write_intent_id)
  if intent is None:self._block("intent_not_found")
  if intent.status!="prepared":self._block("intent_not_prepared")
  if (intent.seller_id,intent.marketplace_id,intent.profile_id)!=(seller,marketplace,profile):self._block("scope_mismatch")
  lifecycle=self.lifecycle.revalidate(seller,marketplace,profile,write_intent_id,True)
  if lifecycle.status!="prepared" or lifecycle.reason_code!="current":self._block("intent_not_current")
  current=self.repository.get_write_intent(seller,marketplace,profile,write_intent_id)
  if current is None or current.status!="prepared" or current.idempotency_key!=intent.idempotency_key:self._block("intent_not_current")
  intent=current
  if intent.scope_type!="keyword":self._block("unsupported_mutation_scope")
  if intent.action_type!="BID_DIRECTION_REVIEW":self._block("unsupported_action")
  if intent.direction not in ("increase","decrease"):self._block("invalid_direction")
  if target_resolution is None:self._block("target_resolution_required")
  if not target_resolution.eligible or target_resolution.status!="eligible_target_resolution":self._block("target_resolution_not_eligible")
  matches=(target_resolution.write_intent_id==intent.write_intent_id and target_resolution.seller_id==seller and target_resolution.marketplace_id==marketplace and target_resolution.profile_id==profile and target_resolution.recommendation_id==intent.recommendation_id and target_resolution.execution_plan_id==intent.execution_plan_id and target_resolution.action_type==intent.action_type and target_resolution.direction==intent.direction and target_resolution.scope_type==intent.scope_type and target_resolution.scope_id==intent.scope_id)
  if not matches:self._block("target_intent_mismatch")
  if target_resolution.ad_product!="SP":self._block("unsupported_ad_product")
  if target_resolution.advertiser_entity_type!="keyword":self._block("unsupported_entity_type")
  if not target_resolution.advertiser_entity_id or target_resolution.advertiser_entity_id!=intent.scope_id:self._block("target_scope_mismatch")
  if target_resolution.mutation_kind!="SP_KEYWORD_BID":self._block("unsupported_mutation_kind")
  try:
   current_value=Decimal(canonical_decimal(intent.current_value));proposed=Decimal(canonical_decimal(intent.proposed_value))
  except ValueError:self._block("invalid_value")
  if not current_value.is_finite() or not proposed.is_finite() or current_value<=0 or proposed<=0:self._block("invalid_value")
  consistent=proposed>current_value if intent.direction=="increase" else proposed<current_value
  maximum=self.safety.config.max_bid_increase_percent if intent.direction=="increase" else self.safety.config.max_bid_decrease_percent
  try:within=self.safety.percentage_within_limit(current_value,proposed,maximum)
  except (DecimalException,ValueError,TypeError):within=False
  if not consistent:self._block("invalid_direction")
  if not (within and self.safety.config.max_single_action_amount>0 and proposed<=self.safety.config.max_single_action_amount and self.safety.config.max_actions_per_run>=1):self._block("hard_limit_violation")
  return self.repository.save_sealed_write_command(AdsSealedWriteCommand.seal(intent,target_resolution,self.now()))
 def list_commands(self,seller,marketplace,profile,status=None,limit=50):
  if status not in (None,"sealed","superseded","cancelled"):raise ValueError("Unsupported sealed-command status")
  return self.repository.list_sealed_write_commands(seller,marketplace,str(profile),status,limit)
