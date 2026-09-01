from datetime import datetime,timezone
from decimal import Decimal
import pytest

from app.amazon_ads.rule_activation_models import AdsRuleActivationRequest
from app.amazon_ads.rule_tuning_models import AdsRuleTuningProposal
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_rule_activation_service import AdsRuleActivationService

NOW=datetime(2026,1,2,tzinfo=timezone.utc)
FULL={"target_acos_percent":"30","min_impressions_for_ctr":"100","low_ctr_percent":"0.3","min_clicks_for_cvr":"10","low_cvr_percent":"2","high_cpc_amount":"50","wasted_spend_threshold":"500"}

@pytest.fixture
def setup(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");service=AdsRuleActivationService(repo,now=lambda:NOW,id_factory=lambda:"activation-1")
 return repo,service

def version(repo,version_id,status="proposed",thresholds=None,source="manual",proposal_id=None,seller="seller",market="market",profile="profile"):
 return repo.create_rule_version(version_id,seller,market,profile,version_id,status,thresholds or FULL,source,"tester",created_at=NOW,source_proposal_id=proposal_id)

def proposal(repo,status="approved_for_future_rule_version",proposal_id="proposal-1",seller="seller",market="market",profile="profile",current="30",proposed="33"):
 item=AdsRuleTuningProposal(proposal_id,seller,market,profile,"old","target_acos_percent",Decimal(current),Decimal(proposed),"increase","TEST","test",40,"medium","proposed",{},NOW)
 repo.save_rule_tuning_proposal(item)
 if status!="proposed":repo.review_rule_tuning_proposal(seller,market,profile,proposal_id,status,NOW)
 return item

def request(target="new",expected="old",confirm=True,**scope):
 return AdsRuleActivationRequest(scope.get("seller","seller"),scope.get("market","market"),scope.get("profile","profile"),target,expected,confirm)

def test_success_archives_previous_activates_target_and_writes_event(setup):
 repo,service=setup;version(repo,"old","active");proposal(repo);values=dict(FULL,target_acos_percent="33");version(repo,"new",thresholds=values,source="tuning_proposal",proposal_id="proposal-1")
 result=service.activate(request())
 assert result.status=="activated" and result.activation_id=="activation-1" and result.previous_rule_version_id=="old" and result.active_rule_version_id=="new" and result.activated_at==NOW
 assert repo.get_rule_version("seller","market","profile","old")["status"]=="archived"
 assert repo.get_rule_version("seller","market","profile","new")["status"]=="active"
 event=repo.get_latest_rule_activation_event("seller","market","profile");assert (event["from_rule_version_id"],event["to_rule_version_id"],event["source_proposal_id"])==("old","new","proposal-1")

def test_confirmation_false_is_blocked(setup):
 repo,service=setup;version(repo,"new")
 assert service.activate(request(expected=None,confirm=False)).status=="blocked"

@pytest.mark.parametrize("status",["rejected","archived"])
def test_non_proposed_status_is_blocked(setup,status):
 repo,service=setup;version(repo,"new",status)
 assert service.activate(request(expected=None)).status=="blocked"

def test_already_active_is_idempotent(setup):
 repo,service=setup;version(repo,"new","active")
 first=service.activate(request(expected="new"));second=service.activate(request(expected="new"))
 assert first.status==second.status=="already_active" and repo.list_rule_activation_events("seller","market","profile")==[]

@pytest.mark.parametrize("status",["proposed","rejected","dismissed"])
def test_unapproved_proposal_is_blocked(setup,status):
 repo,service=setup;proposal(repo,status);version(repo,"new",thresholds=dict(FULL,target_acos_percent="33"),source="tuning_proposal",proposal_id="proposal-1")
 assert service.activate(request(expected=None)).status=="blocked"

@pytest.mark.parametrize("field,value",[("seller","other"),("market","other"),("profile","other")])
def test_scope_mismatch_is_blocked(setup,field,value):
 repo,service=setup;version(repo,"new")
 assert service.activate(request(expected=None,**{field:value})).status=="blocked"

def test_expected_active_match_and_conflicts(setup):
 repo,service=setup;version(repo,"old","active");version(repo,"new")
 assert service.activate(request(expected="stale")).status=="conflict"
 assert service.activate(request(expected=None)).status=="conflict"
 repo2=AdsPerformanceRepository(repo._database_path.parent/"none.db");service2=AdsRuleActivationService(repo2,now=lambda:NOW);version(repo2,"new")
 assert service2.activate(request(expected="missing")).status=="conflict"

@pytest.mark.parametrize("thresholds",[{"target_acos_percent":"bad"},{"unknown":"1"},{"target_acos_percent":"101"}])
def test_invalid_thresholds_are_blocked(setup,thresholds):
 repo,service=setup;version(repo,"new",thresholds=thresholds)
 assert service.activate(request(expected=None)).status=="blocked"

def test_max_relative_change_is_blocked(setup):
 repo,service=setup;proposal(repo,current="30",proposed="45");version(repo,"new",thresholds=dict(FULL,target_acos_percent="45"),source="tuning_proposal",proposal_id="proposal-1")
 assert service.activate(request(expected=None)).status=="blocked"

@pytest.mark.parametrize("boundary",["_activate_rule_version_in_transaction","_insert_activation_event_in_transaction"])
def test_transaction_failure_rolls_back_everything(setup,monkeypatch,boundary):
 repo,service=setup;version(repo,"old","active");version(repo,"new")
 def fail(*args,**kwargs):raise RuntimeError("injected")
 monkeypatch.setattr(repo,boundary,fail)
 assert service.activate(request()).status=="error"
 assert repo.get_rule_version("seller","market","profile","old")["status"]=="active"
 assert repo.get_rule_version("seller","market","profile","new")["status"]=="proposed"
 assert repo.list_rule_activation_events("seller","market","profile")==[]
