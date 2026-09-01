from datetime import datetime,timezone
from decimal import Decimal
from itertools import count
import json
import pytest

from app.amazon_ads.rule_activation_models import AdsRuleActivationRequest,AdsRuleRollbackRequest
from app.amazon_ads.rule_tuning_models import AdsRuleTuningProposal
from app.database.ads_repository import AdsPerformanceRepository
from app.database.connection import get_connection
from app.services.ads_rule_activation_service import AdsRuleActivationService
from app.services.ads_rule_rollback_service import AdsRuleRollbackService

NOW=datetime(2026,1,3,tzinfo=timezone.utc)
FULL={"target_acos_percent":"30","min_impressions_for_ctr":"100","low_ctr_percent":"0.3","min_clicks_for_cvr":"10","low_cvr_percent":"2","high_cpc_amount":"50","wasted_spend_threshold":"500"}

@pytest.fixture
def env(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db")
 activation_ids=count(1);rollback_ids=count(1)
 activation=AdsRuleActivationService(repo,now=lambda:NOW,id_factory=lambda:f"activation-{next(activation_ids)}")
 rollback=AdsRuleRollbackService(repo,now=lambda:NOW,id_factory=lambda:f"rollback-{next(rollback_ids)}")
 return repo,activation,rollback

def version(repo,version_id,status="proposed",thresholds=None,seller="seller",market="market",profile="profile",source="manual",proposal_id=None):
 return repo.create_rule_version(version_id,seller,market,profile,version_id,status,thresholds or FULL,source,"tester",created_at=NOW,source_proposal_id=proposal_id)

def activate(service,target,expected):return service.activate(AdsRuleActivationRequest("seller","market","profile",target,expected,True))
def request(expected="B",confirm=True,**scope):return AdsRuleRollbackRequest(scope.get("seller","seller"),scope.get("market","market"),scope.get("profile","profile"),expected,confirm)

def active_pair(env):
 repo,activation,rollback=env;version(repo,"A","active")
 proposal=AdsRuleTuningProposal("proposal-B","seller","market","profile","A","target_acos_percent",Decimal("30"),Decimal("33"),"increase","TEST","approved test",40,"medium","proposed",{},NOW)
 repo.save_rule_tuning_proposal(proposal);repo.review_rule_tuning_proposal("seller","market","profile","proposal-B","approved_for_future_rule_version",NOW)
 version(repo,"B",thresholds=dict(FULL,target_acos_percent="33"),source="tuning_proposal",proposal_id="proposal-B");assert activate(activation,"B","A").status=="activated";return repo,activation,rollback

def test_basic_success_and_event_content(env):
 repo,_,rollback=active_pair(env);result=rollback.rollback(request())
 assert result.status=="rolled_back" and result.rollback_id=="rollback-1" and result.previous_active_rule_version_id=="B" and result.restored_rule_version_id=="A"
 assert repo.get_rule_version("seller","market","profile","A")["status"]=="active" and repo.get_rule_version("seller","market","profile","B")["status"]=="archived"
 event=repo.get_latest_rule_activation_event("seller","market","profile");assert (event["event_type"],event["from_rule_version_id"],event["to_rule_version_id"],event["seller_id"],event["marketplace_id"],event["profile_id"])==("RULE_VERSION_ROLLED_BACK","B","A","seller","market","profile")

def test_confirmation_false_blocked(env):
 _,_,rollback=active_pair(env);assert rollback.rollback(request(confirm=False)).status=="blocked"

@pytest.mark.parametrize("expected",["stale",None])
def test_stale_or_null_expected_conflicts(env,expected):
 _,_,rollback=active_pair(env);assert rollback.rollback(request(expected=expected)).status=="conflict"

def test_no_history_does_not_restore_arbitrary_archive(env):
 repo,_,rollback=env;version(repo,"old","archived");version(repo,"current","active")
 result=rollback.rollback(request(expected="current"));assert result.status=="no_history" and repo.get_active_rule_version("seller","market","profile")["rule_version_id"]=="current"

@pytest.mark.parametrize("field,value",[("seller","other"),("market","other"),("profile","other")])
def test_scope_isolation(env,field,value):
 _,_,rollback=active_pair(env);assert rollback.rollback(request(**{field:value})).status in ("blocked","conflict")

def corrupt_predecessor(repo,operation):
 with get_connection(repo._database_path) as connection:operation(connection)

@pytest.mark.parametrize("operation",[
 lambda c:c.execute("DELETE FROM ads_rule_versions WHERE rule_version_id='A'"),
 lambda c:c.execute("UPDATE ads_rule_versions SET status='rejected' WHERE rule_version_id='A'"),
 lambda c:c.execute("UPDATE ads_rule_versions SET thresholds_json=? WHERE rule_version_id='A'",('{bad',)),
 lambda c:c.execute("UPDATE ads_rule_versions SET thresholds_json=? WHERE rule_version_id='A'",(json.dumps({"unknown":"1"}),)),
 lambda c:c.execute("UPDATE ads_rule_versions SET thresholds_json=? WHERE rule_version_id='A'",(json.dumps({"target_acos_percent":"101"}),)),
])
def test_invalid_predecessor_is_blocked(env,operation):
 repo,_,rollback=active_pair(env);corrupt_predecessor(repo,operation)
 result=rollback.rollback(request());assert result.status=="blocked" and repo.get_active_rule_version("seller","market","profile")["rule_version_id"]=="B"

@pytest.mark.parametrize("boundary",["_restore_rule_version_in_transaction","_insert_rollback_event_in_transaction"])
def test_atomic_failure_rolls_back_statuses_and_event(env,monkeypatch,boundary):
 repo,_,rollback=active_pair(env);before=len(repo.list_rule_activation_events("seller","market","profile"))
 def fail(*args,**kwargs):raise RuntimeError("injected")
 monkeypatch.setattr(repo,boundary,fail);assert rollback.rollback(request()).status=="error"
 assert repo.get_rule_version("seller","market","profile","B")["status"]=="active" and repo.get_rule_version("seller","market","profile","A")["status"]=="archived"
 assert len(repo.list_rule_activation_events("seller","market","profile"))==before

def test_history_chain_rollback_then_activate_uses_current_activation_edge(env):
 repo,activation,rollback=active_pair(env);assert rollback.rollback(request()).status=="rolled_back"
 version(repo,"C");assert activate(activation,"C","A").status=="activated"
 result=rollback.rollback(request(expected="C"));assert result.status=="rolled_back" and result.restored_rule_version_id=="A"

def test_multi_activation_chain_walks_back_without_blind_oscillation(env):
 repo,activation,rollback=active_pair(env);version(repo,"C");assert activate(activation,"C","B").status=="activated"
 assert rollback.rollback(request(expected="C")).restored_rule_version_id=="B"
 assert rollback.rollback(request(expected="B")).restored_rule_version_id=="A"
 assert rollback.rollback(request(expected="A")).status=="no_history"

def test_repeated_identical_request_is_conflict_and_no_duplicate(env):
 repo,_,rollback=active_pair(env);assert rollback.rollback(request()).status=="rolled_back";count=len(repo.list_rule_activation_events("seller","market","profile"))
 assert rollback.rollback(request()).status=="conflict" and len(repo.list_rule_activation_events("seller","market","profile"))==count

def test_read_only_rollback_status(env):
 repo,_,rollback=active_pair(env);status=rollback.get_rollback_status("seller","market","profile")
 assert status.rollback_available and status.current_rule_version_id=="B" and status.previous_rule_version_id=="A" and repo.get_active_rule_version("seller","market","profile")["rule_version_id"]=="B"
