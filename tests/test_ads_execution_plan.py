from datetime import datetime, timezone
from app.amazon_ads.action_models import AdsRecommendationDecision
from app.amazon_ads.recommendation_models import AdsRecommendation
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_execution_plan_service import AdsExecutionPlanService


def recommendation(code="BID_DECREASE_CANDIDATE"):
    return AdsRecommendation("seller","market","profile","keyword","keyword-1","Keyword",code,"high","high","Review","Summary","Reason",30,{},"Review only")
class Recommendations:
    def __init__(self, current=True, code="BID_DECREASE_CANDIDATE"): self.current=current; self.item=recommendation(code)
    def get_recommendations(self,*args,**kwargs): return [self.item] if self.current else []

def decision(repository, status="approved"):
    now=datetime(2026,1,1,tzinfo=timezone.utc); item=recommendation()
    return repository.save_decision(AdsRecommendationDecision(item.recommendation_id,"seller","market","profile",item.scope_type,item.scope_id,item.recommendation_code,item.title,status,created_at=now,updated_at=now,reviewed_at=now))

def test_approved_current_plan_is_dry_run_and_idempotent(tmp_path):
    repository=AdsPerformanceRepository(tmp_path/"ads.db"); record=decision(repository)
    service=AdsExecutionPlanService(Recommendations(),repository,now=lambda:datetime(2026,1,2,tzinfo=timezone.utc))
    first=service.create_dry_run("seller","market","profile",record.recommendation_id)
    second=service.create_dry_run("seller","market","profile",record.recommendation_id)
    assert first.dry_run is True and first.eligible is True and first.status=="eligible_dry_run"
    assert first.plan_hash==second.plan_hash and len(repository.list_execution_plans("seller","market","profile"))==1
    assert first.current_value is None and first.proposed_value is None

def test_stale_or_unapproved_plan_is_blocked(tmp_path):
    repository=AdsPerformanceRepository(tmp_path/"ads.db"); record=decision(repository,"rejected")
    service=AdsExecutionPlanService(Recommendations(),repository)
    assert service.create_dry_run("seller","market","profile",record.recommendation_id).status=="not_approved"
    repository=AdsPerformanceRepository(tmp_path/"stale.db"); record=decision(repository)
    assert AdsExecutionPlanService(Recommendations(False),repository).create_dry_run("seller","market","profile",record.recommendation_id).status=="stale_recommendation"
