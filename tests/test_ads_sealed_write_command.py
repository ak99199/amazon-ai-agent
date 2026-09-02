from dataclasses import replace
from datetime import datetime,timezone
from decimal import Decimal
import pytest
from app.amazon_ads.write_command_models import AdsSealedWriteCommand,AdsSealedWriteCommandBlockedError
from app.amazon_ads.write_models import AdsWriteConfig
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_sealed_write_command_service import AdsSealedWriteCommandService
from tests.test_ads_exact_value_proposal_service import safety
from tests.test_ads_write_target_resolution import fixtures as target_fixtures

NOW=datetime(2026,2,15,tzinfo=timezone.utc)
class Repo:
 def __init__(self,intent):self.intent=intent;self.commands={}
 def get_write_intent(self,s,m,p,i):return self.intent if self.intent and (self.intent.seller_id,self.intent.marketplace_id,self.intent.profile_id,self.intent.write_intent_id)==(s,m,str(p),i) else None
 def save_sealed_write_command(self,c):return self.commands.setdefault(c.command_hash,c)
 def list_sealed_write_commands(self,s,m,p,status=None,limit=50):return [c for c in self.commands.values() if (c.seller_id,c.marketplace_id,c.profile_id)==(s,m,str(p)) and (status is None or c.status==status)][:limit]
class Lifecycle:
 def __init__(self,status="prepared",reason="current"):self.status=status;self.reason=reason
 def revalidate(self,*args):return type("Result",(),{"status":self.status,"reason_code":self.reason})()
def setup():
 target_service,_,intent,_=target_fixtures();target=target_service.resolve("s","m","p",intent.write_intent_id,True)
 repo=Repo(intent);service=AdsSealedWriteCommandService(repo,Lifecycle(),AdsWriteConfig(True,True,True),safety(),lambda:NOW)
 return service,repo,intent,target
def blocked(service,status,**kwargs):
 with pytest.raises(AdsSealedWriteCommandBlockedError) as error:service.seal("s","m","p",kwargs.pop("id","unused"),**kwargs)
 assert error.value.status==status
def test_confirmation_intent_and_lifecycle_gates():
 service,repo,intent,target=setup();blocked(service,"confirmation_required",id=intent.write_intent_id,target_resolution=target)
 blocked(service,"intent_not_found",id="missing",confirm=True,target_resolution=target)
 for state in ("cancelled","superseded"):
  repo.intent=replace(intent,status=state);blocked(service,"intent_not_prepared",id=intent.write_intent_id,confirm=True,target_resolution=target)
 repo.intent=intent;service.lifecycle=Lifecycle("superseded","stale_recommendation");blocked(service,"intent_not_current",id=intent.write_intent_id,confirm=True,target_resolution=target)
def test_target_and_semantic_mismatches_block():
 service,repo,intent,target=setup();identifier=intent.write_intent_id
 blocked(service,"target_resolution_required",id=identifier,confirm=True)
 blocked(service,"target_resolution_not_eligible",id=identifier,confirm=True,target_resolution=replace(target,eligible=False))
 changes=(("write_intent_id","other","target_intent_mismatch"),("ad_product","SB","unsupported_ad_product"),("advertiser_entity_type","target","unsupported_entity_type"),("advertiser_entity_id","other","target_scope_mismatch"),("mutation_kind","OTHER","unsupported_mutation_kind"))
 for field,value,status in changes:blocked(service,status,id=identifier,confirm=True,target_resolution=replace(target,**{field:value}))
 repo.intent=replace(intent,scope_type="campaign");blocked(service,"unsupported_mutation_scope",id=identifier,confirm=True,target_resolution=target)
def test_decimal_canonical_hash_and_id_are_deterministic():
 service,repo,intent,target=setup();first=service.seal("s","m","p",intent.write_intent_id,True,target)
 repo.intent=replace(intent,current_value="1.000",proposed_value="1.1000");second=service.seal("s","m","p",intent.write_intent_id,True,target)
 assert first.command_hash==second.command_hash and first.command_id==second.command_id
 assert first.expected_current_value=="1" and first.proposed_value=="1.1" and len(repo.commands)==1
 assert all(term not in str(first.public_dict()).lower() for term in ("authorization","access_token","payload","endpoint","url"))
 assert not hasattr(AdsSealedWriteCommandService,"execute_command") and not hasattr(AdsSealedWriteCommandService,"dispatch_command")
def test_invalid_values_and_hard_limits_block():
 for current,proposed,status in (("NaN","1.1","invalid_value"),("Infinity","1.1","invalid_value"),("0","1.1","invalid_value"),("-1","1.1","invalid_value"),("1","0","invalid_value"),("1","-1","invalid_value")):
  service,repo,intent,target=setup();repo.intent=replace(intent,current_value=current,proposed_value=proposed);blocked(service,status,id=intent.write_intent_id,confirm=True,target_resolution=target)
 service,repo,intent,target=setup();service.safety=safety(amount=Decimal("1"));blocked(service,"hard_limit_violation",id=intent.write_intent_id,confirm=True,target_resolution=target)
def test_sqlite_atomic_idempotency_audit_and_isolation(tmp_path):
 service,repo,intent,target=setup();command=service.seal("s","m","p",intent.write_intent_id,True,target);database=AdsPerformanceRepository(tmp_path/"ads.db")
 assert database.save_sealed_write_command(command).command_id==database.save_sealed_write_command(command).command_id
 assert len(database.list_sealed_write_commands("s","m","p"))==1 and database.list_sealed_write_commands("other","m","p")==[] and database.list_sealed_write_commands("s","other","p")==[] and database.list_sealed_write_commands("s","m","other")==[]
 assert len(database.list_sealed_write_command_events("s","m","p",command.command_id))==1
