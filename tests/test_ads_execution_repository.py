from datetime import datetime, timezone
from app.amazon_ads.execution_models import AdsExecutionPlan
from app.database.ads_repository import AdsPerformanceRepository

def plan(seller="seller",market="market",profile="profile"):
 return AdsExecutionPlan("recommendation","decision",seller,market,profile,"keyword","keyword-1","BID_DECREASE_CANDIDATE","BID_DIRECTION_REVIEW","decrease",dry_run=True,eligible=True,status="eligible_dry_run",eligibility_code="eligible_dry_run",eligibility_reason="safe",safety_checks=(),created_at=datetime(2026,1,1,tzinfo=timezone.utc))
def test_execution_plan_repository_is_scoped_and_idempotent(tmp_path):
 repository=AdsPerformanceRepository(tmp_path/"ads.db"); first=repository.save_execution_plan(plan()); second=repository.save_execution_plan(plan())
 assert first.plan_hash==second.plan_hash and len(repository.list_execution_plans("seller","market","profile"))==1
 assert repository.list_execution_plans("other","market","profile")==[]
 assert len(repository.list_execution_events("seller","market","profile",first.stable_execution_plan_id))==1
