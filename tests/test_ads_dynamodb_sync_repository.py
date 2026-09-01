from datetime import date,datetime,timedelta,timezone
import pytest
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.database.ads_dynamodb_repository import AdsDynamoDbRepositoryError,DynamoDbAdsHistoricalRepository
from tests.ads_dynamodb_fakes import Resource
NOW=datetime(2026,2,10,12,tzinfo=timezone.utc)
def run(identifier,started=NOW,status="running",success=False,profile="p",trigger="scheduled",rows=0,error=None):return AdsManualSyncResult(identifier,"historical_campaign_report","s","m",profile,date(2026,2,8),date(2026,2,9),started,started+timedelta(minutes=1) if status!="running" else None,success,status,rows_saved=rows,error_code=error,safe_error_message="safe" if error else None,trigger_source=trigger)
def terminal(value,status="completed",success=True,rows=2,error=None):return AdsManualSyncResult(**{**value.__dict__,"finished_at":value.started_at+timedelta(minutes=1),"status":status,"success":success,"rows_saved":rows,"error_code":error,"safe_error_message":"safe" if error else None})
def repository():
 resource=Resource();return DynamoDbAdsHistoricalRepository(resource.Table("performance"),resource.Table("runs"),resource.client),resource

def test_atomic_start_lock_concurrency_and_profile_isolation():
 repo,resource=repository();first=run("one");second=run("two");other=run("other",profile="other")
 assert repo.start_sync_run_if_idle(first,NOW-timedelta(hours=1)) and not repo.start_sync_run_if_idle(second,NOW-timedelta(hours=1)) and repo.start_sync_run_if_idle(other,NOW-timedelta(hours=1))
 assert repo.active_sync_run("s","m","p").sync_id=="one" and repo.active_sync_run("s","m","other").sync_id=="other"
 assert {item["sync_id"] for item in resource.store["runs"].values() if item["run_key"].startswith("RUN#")}=={"one","other"}
 assert len({repo.scope_key("s","m","p"),repo.scope_key("s","m","other"),repo.scope_key("other","m","p"),repo.scope_key("s","other","p")})==4

def test_success_failure_summaries_history_and_observability():
 repo,_=repository();manual=run("manual",NOW-timedelta(hours=3),trigger="manual");assert repo.start_sync_run_if_idle(manual,NOW-timedelta(days=1));repo.save_sync_run(terminal(manual))
 success=run("scheduled",NOW-timedelta(hours=2));assert repo.start_sync_run_if_idle(success,NOW-timedelta(days=1));repo.save_sync_run(terminal(success,rows=4))
 failed=run("failed",NOW-timedelta(hours=1));assert repo.start_sync_run_if_idle(failed,NOW-timedelta(days=1));repo.save_sync_run(terminal(failed,"failed",False,0,"remote_error"))
 assert repo.active_sync_run("s","m","p") is None and repo.latest_successful_sync("s","m","p").sync_id=="scheduled"
 assert repo.latest_successful_sync("s","m","p","historical_campaign_report","scheduled").sync_id=="scheduled" and repo.latest_failed_sync("s","m","p").sync_id=="failed"
 assert [item.sync_id for item in repo.list_sync_runs("s","m","p",2)]==["failed","scheduled"]
 assert repo.count_sync_runs_since("s","m","p",NOW-timedelta(hours=2,minutes=30))==2 and repo.aggregate_sync_counts_since("s","m","p",NOW-timedelta(days=1))==(6,0)

def test_stale_recovery_is_exact_idempotent_and_wins_terminal_race():
 repo,_=repository();active=run("stale",NOW-timedelta(hours=6));assert repo.start_sync_run_if_idle(active,NOW-timedelta(days=1))
 assert repo.finalize_stale_sync_run("stale","s","m","p",NOW-timedelta(hours=6),NOW) and not repo.finalize_stale_sync_run("stale","s","m","p",NOW-timedelta(hours=6),NOW)
 recovered=repo.list_sync_runs("s","m","p",1)[0];assert recovered.status=="failed" and recovered.error_code=="stale_run_timeout" and repo.active_sync_run("s","m","p") is None
 with pytest.raises(AdsDynamoDbRepositoryError):repo.save_sync_run(terminal(active))
 assert repo.list_sync_runs("s","m","p",1)[0].status=="failed"

def test_fresh_run_is_not_stale():
 repo,_=repository();active=run("fresh",NOW-timedelta(hours=5,minutes=59));assert repo.start_sync_run_if_idle(active,NOW-timedelta(days=1))
 assert not repo.finalize_stale_sync_run("fresh","s","m","p",NOW-timedelta(hours=6),NOW) and repo.active_sync_run("s","m","p").sync_id=="fresh"
