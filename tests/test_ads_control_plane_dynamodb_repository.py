from datetime import datetime,timezone
from decimal import Decimal
import pytest
from copy import deepcopy
from dataclasses import replace
from app.database.ads_control_plane_dynamodb_repository import DynamoDbAdsControlPlaneRepository,AdsControlPlaneRepositoryError
from tests.test_ads_write_preflight_service import fixtures
from app.amazon_ads.rule_tuning_models import AdsRuleTuningProposal
from tests.test_ads_write_intent_revalidation import setup
from tests.test_ads_sealed_write_command import setup as command_setup

class Client:
 def __init__(self,table,fail=False):self.calls=[];self.fail=fail;self.table=table
 def transact_write_items(self,TransactItems):
  self.calls.append(TransactItems)
  if self.fail:raise RuntimeError("fake")
  candidate=deepcopy(self.table.items)
  for action in TransactItems:
   name,payload=next(iter(action.items()));source=payload.get("Item") or payload.get("Key");key=(source["PK"],source["SK"]);old=candidate.get(key);condition=payload.get("ConditionExpression","")
   names=payload.get("ExpressionAttributeNames",{});values=payload.get("ExpressionAttributeValues",{})
   if "attribute_not_exists" in condition and old is not None:raise RuntimeError("conditional")
   if condition.startswith("#"):
    left,right=[part.strip() for part in condition.split("=",1)]
    if old is None or old.get(names.get(left,left))!=values[right]:raise RuntimeError("conditional")
   if name=="Put":candidate[key]=deepcopy(payload["Item"])
   else:
    updated=deepcopy(old)
    for assignment in payload["UpdateExpression"].removeprefix("SET ").split(","):
     field,value=[part.strip() for part in assignment.split("=")];updated[names.get(field,field)]=values[value]
    candidate[key]=updated
  self.table.items=candidate
class Table:
 name="control"
 def __init__(self):self.items={};self.query_calls=[]
 def get_item(self,Key,ConsistentRead):return {"Item":self.items.get((Key["PK"],Key["SK"]))}
 def query(self,**kwargs):
  self.query_calls.append(kwargs);values=kwargs["ExpressionAttributeValues"];rows=[deepcopy(v) for (pk,sk),v in self.items.items() if pk==values[":pk"] and sk.startswith(values[":prefix"])]
  rows.sort(key=lambda v:v["SK"],reverse=not kwargs.get("ScanIndexForward",True));return {"Items":rows[:kwargs["Limit"]]}

def repository(fail=False):
 table=Table();return DynamoDbAdsControlPlaneRepository(table,Client(table,fail),"control")

def intent():
 maker,_,_,_,_,proposal,preflight=__import__("tests.test_ads_write_intent_service",fromlist=["trusted"]).trusted()
 return maker.prepare("s","m","p","plan",True,proposal,preflight)
def test_scoped_keys_serialization_and_atomic_intent_event():
 repo=repository();client=repo.client;item=intent();repo.save_write_intent(item)
 tx=client.calls[0];record=tx[0]["Put"]["Item"];event=tx[1]["Put"]["Item"]
 assert record["PK"]=="SELLER#s#MARKETPLACE#m#PROFILE#p" and record["SK"].startswith("WRITE_INTENT#")
 assert isinstance(record["created_at"],str) and event["event_type"]=="WRITE_INTENT_PREPARED"
 assert "access_token" not in str(record).lower() and len(tx)==2
def test_sealed_command_and_event_are_one_transaction():
 service,_,item,target=command_setup();command=service.seal("s","m","p",item.write_intent_id,True,target)
 repo=repository();client=repo.client;repo.save_sealed_write_command(command)
 assert len(client.calls)==1 and len(client.calls[0])==2 and client.calls[0][1]["Put"]["Item"]["event_type"]=="WRITE_COMMAND_SEALED"
def test_transaction_failure_is_safe_and_scope_key_isolated():
 repo=repository(True)
 with pytest.raises(AdsControlPlaneRepositoryError):repo.save_write_intent(intent())
 assert repo.scope_key("s","m","p")!=repo.scope_key("other","m","p")!=repo.scope_key("other","other","p")

def test_decision_behavior_events_filter_and_scope_isolation():
 repo=repository();_,decision,_=fixtures();repo.save_decision(decision)
 assert repo.get_decision("s","m","p",decision.recommendation_id).status=="approved"
 assert len(repo.list_decisions("s","m","p","approved"))==1 and repo.list_decisions("other","m","p")==[]
 assert len(repo.list_decision_events("s","m","p",decision.recommendation_id))==1
 repo.save_decision(decision);assert len(repo.list_decision_events("s","m","p",decision.recommendation_id))==1

def test_execution_plan_domain_lookup_events_idempotency_and_scope():
 repo=repository();_,_,plan=fixtures();repo.save_execution_plan(plan)
 assert repo.get_execution_plan("s","m","p",plan.plan_hash).stable_execution_plan_id=="plan"
 assert len(repo.list_execution_plans("s","m","p"))==1 and repo.list_execution_plans("s","other","p")==[]
 assert len(repo.list_execution_events("s","m","p","plan"))==1
 repo.save_execution_plan(plan);assert len(repo.list_execution_events("s","m","p","plan"))==1

def test_write_intent_lists_filters_transitions_events_and_no_resurrection():
 repo=repository();value=intent();repo.save_write_intent(value)
 assert repo.get_write_intent("s","m","p",value.write_intent_id).current_value==value.current_value
 assert len(repo.list_write_intents("s","m","p","prepared"))==1 and repo.list_write_intents("s","m","other")==[]
 changed=repo.transition_write_intent("s","m","p",value.write_intent_id,"superseded","WRITE_INTENT_SUPERSEDED",value.created_at)
 assert changed.status=="superseded" and len(repo.list_write_intent_events("s","m","p",value.write_intent_id))==2
 with pytest.raises(AdsControlPlaneRepositoryError):repo.transition_write_intent("s","m","p",value.write_intent_id,"cancelled","WRITE_INTENT_CANCELLED",value.created_at)

def test_sealed_command_round_trip_list_filter_event_and_duplicate():
 service,_,item,target=command_setup();command=service.seal("s","m","p",item.write_intent_id,True,target);repo=repository()
 repo.save_sealed_write_command(command);repo.save_sealed_write_command(command)
 listed=repo.list_sealed_write_commands("s","m","p","sealed")
 assert len(listed)==1 and listed[0].command_hash==command.command_hash and isinstance(listed[0].created_at,datetime)
 assert len(repo.list_sealed_write_command_events("s","m","p",command.command_id))==1 and repo.list_sealed_write_commands("other","m","p")==[]

def test_prefix_queries_no_scan_and_nested_decimal_bool_null_serialization():
 repo=repository();_,decision,_=fixtures();decision=replace(decision,recommendation_snapshot={"money":Decimal("1.25"),"flags":[True,False],"optional":None});repo.save_decision(decision)
 value=repo.get_decision("s","m","p",decision.recommendation_id)
 assert value.recommendation_snapshot=={"money":Decimal("1.25"),"flags":[True,False],"optional":None}
 repo.list_decisions("s","m","p",limit=1);assert repo.table.query_calls and all("begins_with" in call["KeyConditionExpression"] for call in repo.table.query_calls)
 assert not hasattr(repo.table,"scan")

def test_rule_version_create_read_list_active_and_status_update():
 repo=repository();at=datetime(2026,2,1,tzinfo=timezone.utc)
 repo.create_rule_version("v1","s","m","p","One","proposed",{"target":Decimal("1.25")},"test","admin",None,at)
 assert repo.get_rule_version("s","m","p","v1")["thresholds"]["target"]==Decimal("1.25")
 repo.update_rule_version_status("s","m","p","v1","active",at,at)
 assert repo.get_active_rule_version("s","m","p")["rule_version_id"]=="v1" and len(repo.list_rule_versions("s","m","p"))==1

def test_rule_activation_rollback_atomic_history_and_conflicts():
 repo=repository();at=datetime(2026,2,1,tzinfo=timezone.utc)
 repo.create_rule_version("old","s","m","p","Old","active",{"x":Decimal("1")},"test","admin",None,at,activated_at=at)
 repo.create_rule_version("new","s","m","p","New","proposed",{"x":Decimal("2")},"test","admin",None,at)
 assert repo.activate_rule_version("s","m","p","new","wrong","e0",at) is None
 result=repo.activate_rule_version("s","m","p","new","old","e1",at)
 assert result["target"]["status"]=="active" and repo.get_rule_version("s","m","p","old")["status"]=="archived"
 assert repo.get_rollback_candidate("s","m","p","new")["rule_version_id"]=="old"
 assert repo.get_rollback_candidate("other","m","p","new") is None
 assert repo.rollback_rule_version("s","m","p","wrong","e2",at)["status"]=="conflict"
 assert repo.rollback_rule_version("s","m","p","new","e3",at)["status"]=="rolled_back"
 assert repo.get_active_rule_version("s","m","p")["rule_version_id"]=="old"
 assert [e["event_type"] for e in repo.list_rule_activation_events("s","m","p")]==["RULE_VERSION_ROLLED_BACK","RULE_VERSION_ACTIVATED"]

def test_rule_tuning_create_review_events_decimal_and_invalid_status():
 repo=repository();at=datetime(2026,2,1,tzinfo=timezone.utc);proposal=AdsRuleTuningProposal("tp","s","m","p","v1","high_cpc_amount",Decimal("1.20"),Decimal("1.10"),"decrease","reason","summary",10,"high","proposed",{"nested":[Decimal("2.5"),True,None]},at)
 repo.save_rule_tuning_proposal(proposal);repo.save_rule_tuning_proposal(proposal)
 stored=repo.get_rule_tuning_proposal("s","m","p","tp")
 assert stored["current_value"]==Decimal("1.20") and stored["evaluation_summary"]["nested"]==[Decimal("2.5"),True,None]
 assert len(repo.list_rule_tuning_proposals("s","m","p"))==1
 assert repo.review_rule_tuning_proposal("s","m","p","tp","rejected",at)=="rejected"
 assert repo.get_rule_tuning_proposal("s","m","p","tp")["status"]=="rejected"
 assert len(repo._query("s","m","p","RULE_TUNING_EVENT#",200,True))==2
 with pytest.raises(ValueError):repo.review_rule_tuning_proposal("s","m","p","tp","invalid",at)

def test_atomic_failures_leave_no_partial_observable_state():
 repo=repository(True);at=datetime(2026,2,1,tzinfo=timezone.utc)
 with pytest.raises(AdsControlPlaneRepositoryError):repo.create_rule_version("v","s","m","p","V","proposed",{},"test","admin",None,at)
 assert repo.get_rule_version("s","m","p","v") is None and repo.table.items=={}
