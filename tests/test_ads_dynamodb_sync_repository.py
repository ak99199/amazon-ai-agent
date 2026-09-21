from dataclasses import replace
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

def test_ingestion_reads_return_empty_results():
 repo,_=repository()
 assert [repo.count_ingestion_runs("s","m","p",success) for success in (None,True,False)]==[0,0,0]
 assert repo.get_latest_ingestion_run("s","m","p") is None
 assert repo.get_latest_successful_ingestion_run("s","m","p") is None

def test_ingestion_reads_count_only_terminal_history_and_return_latest_mappings():
 repo,_=repository();repo.sync_runs_table.page_size=2
 successful=run("success",NOW-timedelta(hours=3));assert repo.start_sync_run_if_idle(successful,NOW-timedelta(days=1))
 successful=terminal(successful,rows=4);repo.save_sync_run(successful)
 failed=run("failure",NOW-timedelta(hours=2));assert repo.start_sync_run_if_idle(failed,NOW-timedelta(days=1))
 failed=replace(terminal(failed,"failed",False,0,"remote_error"),rows_failed=3);repo.save_sync_run(failed)
 assert repo.start_sync_run_if_idle(run("unfinished",NOW),NOW-timedelta(days=1))
 assert [repo.count_ingestion_runs("s","m","p",success) for success in (None,True,False)]==[2,1,1]
 latest=repo.get_latest_ingestion_run("s","m","p");latest_success=repo.get_latest_successful_ingestion_run("s","m","p")
 assert latest["run_id"]=="failure" and latest["success"] is False
 assert latest["finished_at"]==failed.finished_at.isoformat() and latest["rows_saved"]==0 and latest["rows_failed"]==3
 assert latest_success["run_id"]=="success" and latest_success["success"] is True
 assert latest_success["finished_at"]==successful.finished_at.isoformat() and latest_success["rows_saved"]==4
 assert all(call["ConsistentRead"] and call["ExpressionAttributeValues"]=={":scope":repo.scope_key("s","m","p"),":prefix":"RUN#"} for call in repo.sync_runs_table.query_calls)
 assert any("ExclusiveStartKey" in call for call in repo.sync_runs_table.query_calls)

@pytest.mark.parametrize("scope_field",["seller_id","marketplace_id","profile_id"])
def test_ingestion_reads_isolate_each_scope_component(scope_field):
 repo,_=repository();own=run("own",NOW-timedelta(hours=3))
 assert repo.start_sync_run_if_idle(own,NOW-timedelta(days=1));repo.save_sync_run(terminal(own,rows=2))
 for identifier,hours,success in (("other-success",2,True),("other-failure",1,False)):
  other=replace(run(identifier,NOW-timedelta(hours=hours)),**{scope_field:"other"})
  assert repo.start_sync_run_if_idle(other,NOW-timedelta(days=1))
  repo.save_sync_run(terminal(other,"completed" if success else "failed",success,9))
 scope=tuple("other" if field==scope_field else value for field,value in (("seller_id","s"),("marketplace_id","m"),("profile_id","p")))
 assert [repo.count_ingestion_runs("s","m","p",success) for success in (None,True,False)]==[1,1,0]
 assert repo.get_latest_ingestion_run("s","m","p")["run_id"]=="own"
 assert repo.get_latest_successful_ingestion_run("s","m","p")["run_id"]=="own"
 assert repo.count_ingestion_runs(*scope)==2
 assert repo.get_latest_ingestion_run(*scope)["run_id"]=="other-failure"
 assert repo.get_latest_successful_ingestion_run(*scope)["run_id"]=="other-success"

def test_ingestion_reads_paginate_beyond_a_thousand_history_records():
 repo,resource=repository();repo.sync_runs_table.page_size=250
 for index in range(1003):
  value=terminal(run(f"done-{index}",NOW-timedelta(minutes=index+1002)),"completed" if index%2==0 else "failed",index%2==0)
  item=repo._run_item(value);resource.store["runs"][(item["scope_key"],item["run_key"])]=item
 for index in range(1001):
  item=repo._run_item(run(f"unfinished-{index}",NOW-timedelta(minutes=index)))
  resource.store["runs"][(item["scope_key"],item["run_key"])]=item
 assert [repo.count_ingestion_runs("s","m","p",success) for success in (None,True,False)]==[1003,502,501]
 assert repo.get_latest_ingestion_run("s","m","p")["run_id"]=="done-0"
 assert sum("ExclusiveStartKey" in call for call in repo.sync_runs_table.query_calls)>4

@pytest.mark.parametrize("method",["count_ingestion_runs","get_latest_ingestion_run","get_latest_successful_ingestion_run"])
def test_ingestion_reads_sanitize_storage_failures(monkeypatch,method):
 repo,_=repository()
 def fail(**kwargs):raise RuntimeError("private-storage-detail")
 monkeypatch.setattr(repo.sync_runs_table,"get_item" if method=="get_latest_successful_ingestion_run" else "query",fail)
 with pytest.raises(AdsDynamoDbRepositoryError) as failure:getattr(repo,method)("s","m","p")
 assert "private-storage-detail" not in str(failure.value)
 assert failure.value.__cause__ is None and failure.value.__suppress_context__

@pytest.mark.parametrize("method",["get_latest_ingestion_run","get_latest_successful_ingestion_run"])
@pytest.mark.parametrize("field",["started_at","rows_saved"])
def test_ingestion_reads_sanitize_malformed_stored_values(method,field):
 repo,resource=repository();value=run("malformed",NOW-timedelta(hours=1))
 assert repo.start_sync_run_if_idle(value,NOW-timedelta(days=1));repo.save_sync_run(terminal(value))
 key="SUMMARY#SUCCESS#ANY" if method=="get_latest_successful_ingestion_run" else repo.run_key(value)
 resource.store["runs"][(repo.scope_key("s","m","p"),key)][field]="private-stored-detail"
 with pytest.raises(AdsDynamoDbRepositoryError) as failure:getattr(repo,method)("s","m","p")
 assert "private-stored-detail" not in str(failure.value)
 assert failure.value.__cause__ is None and failure.value.__suppress_context__
