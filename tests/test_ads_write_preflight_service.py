from dataclasses import replace
from datetime import datetime,timezone
from app.amazon_ads.action_models import AdsRecommendationDecision
from app.amazon_ads.execution_models import AdsExecutionPlan
from app.amazon_ads.recommendation_models import AdsRecommendation
from app.amazon_ads.write_models import AdsWriteConfig
from app.services.ads_write_preflight_service import AdsWritePreflightService
NOW=datetime(2026,2,10,tzinfo=timezone.utc)
def recommendation(code="BID_INCREASE_CANDIDATE"):
 return AdsRecommendation("s","m","p","campaign","c","Campaign",code,"medium","high","title","summary","reason",30,{},"review",suggested_bid_direction="increase",created_at=NOW)
def fixtures(**changes):
 current=recommendation();decision=AdsRecommendationDecision(current.recommendation_id,"s","m","p","campaign","c",current.recommendation_code,"title","approved",decision_id="decision",created_at=NOW,updated_at=NOW,reviewed_at=NOW)
 plan=AdsExecutionPlan(current.recommendation_id,"decision","s","m","p","campaign","c",current.recommendation_code,"BID_DIRECTION_REVIEW","increase",None,None,True,True,"eligible_dry_run","eligible_dry_run","safe",(),NOW,"plan")
 return current,decision,replace(plan,**changes)
class Repo:
 def __init__(self,plan,decision):self.plan=plan;self.decision=decision
 def list_execution_plans(self,*args):return [] if self.plan is None else [self.plan]
 def get_decision(self,*args):return self.decision
class Recommendations:
 def __init__(self,current):self.current=current;self.calls=[]
 def get_recommendations(self,*args):self.calls.append(args);return [] if self.current is None else [self.current]
def run(config=AdsWriteConfig(True,True,True),approval="approved",current_marker="default",decision_marker="default",plan_marker="default"):
 current,decision,plan=fixtures();current=current if current_marker=="default" else current_marker;decision=decision if decision_marker=="default" else decision_marker;plan=plan if plan_marker=="default" else plan_marker
 service=AdsWritePreflightService(Recommendations(current),Repo(plan,decision),config,approval,now=lambda:NOW);return service.preflight("s","m","p","plan",True)

def test_default_and_malformed_write_configuration_fail_closed(monkeypatch):
 monkeypatch.delenv("AMAZON_ADS_WRITE_ENABLED",raising=False);monkeypatch.delenv("AMAZON_ADS_WRITE_DRY_RUN_ONLY",raising=False);assert not AdsWriteConfig.from_environment().enabled
 monkeypatch.setenv("AMAZON_ADS_WRITE_ENABLED","maybe");assert run(AdsWriteConfig.from_environment()).status=="write_disabled"
 monkeypatch.setenv("AMAZON_ADS_WRITE_ENABLED","true");monkeypatch.setenv("AMAZON_ADS_WRITE_DRY_RUN_ONLY","false");assert run(AdsWriteConfig.from_environment()).status=="dry_run_only"

def test_approval_decision_plan_and_current_recommendation_gates():
 assert run(approval="pending").status=="approval_pending"
 assert run(decision_marker=replace(fixtures()[1],status="rejected")).status=="decision_not_approved"
 assert run(plan_marker=None).status=="plan_not_found"
 assert run(plan_marker=replace(fixtures()[2],eligible=False)).status=="plan_not_eligible"
 assert run(current_marker=None).status=="stale_recommendation"

def test_scope_supported_action_and_exact_value_gates():
 assert run(plan_marker=replace(fixtures()[2],seller_id="other")).status=="scope_mismatch"
 assert run(plan_marker=replace(fixtures()[2],marketplace_id="other")).status=="scope_mismatch"
 assert run(plan_marker=replace(fixtures()[2],profile_id="other")).status=="scope_mismatch"
 assert run(plan_marker=replace(fixtures()[2],action_type="UNSUPPORTED_REVIEW")).status=="unsupported_action"
 result=run();assert result.status=="exact_value_required" and not result.eligible and result.dry_run

def test_preflight_is_deterministic_safe_and_has_no_transport():
 first=run();second=run();assert first.preflight_id==second.preflight_id and first.created_at==NOW
 public=first.public_dict();assert "secret" not in str(public).lower() and "authorization" not in str(public).lower() and "access_token" not in str(public).lower()
 assert not hasattr(AdsWritePreflightService,"execute") and not hasattr(AdsWritePreflightService,"apply") and not hasattr(AdsWritePreflightService,"push")
def test_exact_bid_values_still_require_decimal_safe_hard_limits():
 assert run(plan_marker=replace(fixtures()[2],current_value="1.00",proposed_value="1.50")).status=="hard_limit_violation"
 assert run(plan_marker=replace(fixtures()[2],current_value="1.00",proposed_value="1.10")).status=="hard_limit_violation"
