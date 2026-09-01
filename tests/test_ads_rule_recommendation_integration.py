from datetime import date,datetime,timezone
from decimal import Decimal
from itertools import count
import pytest
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.amazon_ads.rule_activation_models import AdsRuleActivationRequest,AdsRuleRollbackRequest
from app.amazon_ads.rule_tuning_models import AdsRuleTuningProposal
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_recommendation_service import AdsRecommendationService
from app.services.ads_rule_activation_service import AdsRuleActivationService
from app.services.ads_rule_rollback_service import AdsRuleRollbackService
from app.services.ads_signal_service import AdsRecommendationThresholds,AdsSignalService

NOW=datetime(2026,2,1,tzinfo=timezone.utc)
FULL={"target_acos_percent":"30","min_impressions_for_ctr":"100","low_ctr_percent":"0.3","min_clicks_for_cvr":"10","low_cvr_percent":"2","high_cpc_amount":"50","wasted_spend_threshold":"500"}

def rows():
 return [AdsPerformanceDaily("seller","market","profile",date(2026,1,day),"SP","campaign","Campaign",keyword_id="keyword",keyword_text="Keyword",search_term="term",impressions=10,clicks=5,spend=Decimal("28"),orders=1,units=1,sales=Decimal("100")) for day in range(1,15)]

def seed(repo):
 for row in rows():repo.save(row)

def codes(service):return {item.recommendation_code for item in service.get_campaign_recommendations("seller","market","profile",window=30,reference_date=date(2026,1,14))}

def create_version(repo,version_id,status,threshold):return repo.create_rule_version(version_id,"seller","market","profile",f"Version {version_id}",status,dict(FULL,target_acos_percent=str(threshold)),"manual","tester",created_at=NOW)

def test_no_active_output_matches_pre_version_signal_source(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");seed(repo);now=lambda:NOW
 integrated=AdsRecommendationService(repo,now=now).get_campaign_recommendations("seller","market","profile",window=30,reference_date=date(2026,1,14))
 legacy=AdsRecommendationService(repo,signals=AdsSignalService(AdsRecommendationThresholds.from_environment()),now=now).get_campaign_recommendations("seller","market","profile",window=30,reference_date=date(2026,1,14))
 assert [(x.recommendation_code,x.recommendation_id) for x in integrated]==[(x.recommendation_code,x.recommendation_id) for x in legacy]
 assert all(x.rule_version_id is None and x.rule_version_source=="environment" for x in integrated)

@pytest.mark.parametrize("expected,impressions,clicks,spend,orders,sales",[("HIGH_ACOS",50,20,"50",1,"100"),("LOW_CTR",1000,2,"10",1,"100"),("LOW_CVR",50,20,"1",0,"100"),("WASTED_SPEND",50,20,"50",0,"0"),("KEEP_STABLE",50,20,"30",5,"100")])
def test_no_active_preserves_representative_baseline_formulas(tmp_path,expected,impressions,clicks,spend,orders,sales):
 repo=AdsPerformanceRepository(tmp_path/"ads.db")
 for day in range(1,15):repo.save(AdsPerformanceDaily("seller","market","profile",date(2026,1,day),"SP","campaign","Campaign",impressions=impressions,clicks=clicks,spend=Decimal(spend),orders=orders,units=orders,sales=Decimal(sales)))
 integrated=AdsRecommendationService(repo,now=lambda:NOW);legacy=AdsRecommendationService(repo,signals=AdsSignalService(AdsRecommendationThresholds.from_environment()),now=lambda:NOW)
 assert codes(integrated)==codes(legacy) and expected in codes(integrated)

def test_active_threshold_changes_source_not_formula_or_identity(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");seed(repo);create_version(repo,"A","active",25);service=AdsRecommendationService(repo,now=lambda:NOW)
 output=service.get_campaign_recommendations("seller","market","profile",window=30,reference_date=date(2026,1,14));by_code={item.recommendation_code:item for item in output}
 assert "HIGH_ACOS" in by_code and "BID_DECREASE_CANDIDATE" in by_code
 assert all(item.rule_version_id=="A" and item.rule_version_name=="Version A" and item.rule_version_source=="manual" for item in output)
 identity=by_code["HIGH_ACOS"].recommendation_id;assert by_code["HIGH_ACOS"].public_dict()["rule_version_id"]=="A" and identity==by_code["HIGH_ACOS"].recommendation_id

def test_activation_and_rollback_take_effect_next_evaluation_without_restart(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");seed(repo);create_version(repo,"A","active",30)
 proposal=AdsRuleTuningProposal("proposal-B","seller","market","profile","A","target_acos_percent",Decimal("30"),Decimal("25"),"decrease","TEST","test",40,"medium","proposed",{},NOW);repo.save_rule_tuning_proposal(proposal);repo.review_rule_tuning_proposal("seller","market","profile","proposal-B","approved_for_future_rule_version",NOW)
 repo.create_rule_version("B","seller","market","profile","Version B","proposed",dict(FULL,target_acos_percent="25"),"tuning_proposal","tester",created_at=NOW,source_proposal_id="proposal-B")
 ids=count(1);activation=AdsRuleActivationService(repo,now=lambda:NOW,id_factory=lambda:f"activation-{next(ids)}");rollback=AdsRuleRollbackService(repo,now=lambda:NOW,id_factory=lambda:"rollback-1");service=AdsRecommendationService(repo,now=lambda:NOW)
 assert "HIGH_ACOS" not in codes(service)
 assert activation.activate(AdsRuleActivationRequest("seller","market","profile","B","A",True)).status=="activated"
 active=service.get_campaign_recommendations("seller","market","profile",window=30,reference_date=date(2026,1,14));assert "HIGH_ACOS" in {x.recommendation_code for x in active} and all(x.rule_version_id=="B" for x in active)
 assert rollback.rollback(AdsRuleRollbackRequest("seller","market","profile","B",True)).status=="rolled_back"
 restored=service.get_campaign_recommendations("seller","market","profile",window=30,reference_date=date(2026,1,14));assert "HIGH_ACOS" not in {x.recommendation_code for x in restored} and all(x.rule_version_id=="A" for x in restored)

def test_activation_and_rollback_do_not_rewrite_decision_history(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.initialize()
 from app.database.connection import get_connection
 with get_connection(repo._database_path) as connection:
  connection.execute("INSERT INTO ads_recommendation_decisions(decision_id,recommendation_id,seller_id,marketplace_id,profile_id,scope_type,scope_id,recommendation_code,recommendation_title,status,review_source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",("d","r","seller","market","profile","campaign","campaign","KEEP_STABLE","Keep stable","approved","human",NOW.isoformat(),NOW.isoformat()))
 before=repo.get_decision("seller","market","profile","r");create_version(repo,"A","active",30);create_version(repo,"B","proposed",25)
 activation=AdsRuleActivationService(repo,now=lambda:NOW,id_factory=lambda:"activation");rollback=AdsRuleRollbackService(repo,now=lambda:NOW,id_factory=lambda:"rollback")
 assert activation.activate(AdsRuleActivationRequest("seller","market","profile","B","A",True)).status=="activated";assert rollback.rollback(AdsRuleRollbackRequest("seller","market","profile","B",True)).status=="rolled_back"
 after=repo.get_decision("seller","market","profile","r");assert (after.status,after.stable_decision_id,after.updated_at)==(before.status,before.stable_decision_id,before.updated_at)
