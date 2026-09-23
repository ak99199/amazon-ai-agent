from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
import sqlite3
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_manual_historical_sync_service import HISTORICAL_SYNC_MODE
from app.services.ads_sync_gate_service import AdsSyncGateService
NOW=datetime(2026,2,10,tzinfo=timezone.utc)
def run(identifier,seller="s",profile="p",status="running",success=False,started=NOW,mode=HISTORICAL_SYNC_MODE):return AdsManualSyncResult(identifier,mode,seller,"m",profile,date(2026,2,8),date(2026,2,9),started,started if status not in ("running","starting") else None,success,status)
def test_atomic_start_blocks_same_scope_but_not_different_profile(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");assert repo.start_sync_run_if_idle(run("one"),NOW-timedelta(minutes=30));assert not repo.start_sync_run_if_idle(run("two"),NOW-timedelta(minutes=30));assert repo.start_sync_run_if_idle(run("other",profile="other"),NOW-timedelta(minutes=30))
def test_history_is_mode_filtered_scoped_bounded_and_latest_first(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_sync_run(run("old",status="completed",success=True,started=NOW-timedelta(minutes=2)));repo.save_sync_run(run("new",status="failed",started=NOW-timedelta(minutes=1)));repo.save_sync_run(run("general",status="completed",success=True,mode="live"));repo.save_sync_run(run("other",seller="other",status="completed",success=True))
 assert [item.sync_id for item in repo.list_sync_runs("s","m","p",1,HISTORICAL_SYNC_MODE)]==["new"]
def test_cooldown_anchors_success_only_and_expires(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_sync_run(run("failed",status="failed",started=NOW-timedelta(seconds=10)));gate=AdsSyncGateService(AdsSettings("i","s","r","p","FE"),repo,AdsLiveReadConfig(True,False),"approved",lambda:NOW,cooldown_seconds=60);assert gate.evaluate("s","m",start_date=date(2026,2,8),end_date=date(2026,2,9)).allowed
 repo.save_sync_run(run("success",status="completed",success=True,started=NOW-timedelta(seconds=10)));assert gate.evaluate("s","m",start_date=date(2026,2,8),end_date=date(2026,2,9)).status_code=="blocked_cooldown"
 expired=AdsSyncGateService(AdsSettings("i","s","r","p","FE"),repo,AdsLiveReadConfig(True,False),"approved",lambda:NOW+timedelta(seconds=61),cooldown_seconds=60);assert expired.evaluate("s","m",start_date=date(2026,2,8),end_date=date(2026,2,9)).allowed

def test_report_state_round_trip_claim_and_conditional_finalize(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");value=replace(run("async"),amazon_report_status="creating")
 assert repo.start_sync_run_if_idle(value,NOW-timedelta(days=1))
 created=replace(value,report_id="private-report",report_type_id="spCampaigns",amazon_report_status="pending",report_created_at=NOW)
 assert repo.save_created_report(created);claimed=repo.claim_report_check("s","m","p","async","claim",NOW)
 assert claimed.report_id=="private-report" and claimed.report_claim=="claim"
 checked=replace(claimed,amazon_report_status="processing",report_last_checked_at=NOW)
 assert repo.save_report_check(checked,"claim") and repo.active_sync_run("s","m","p").amazon_report_status=="processing"
 assert "report_id" not in created.public_dict() and "report_claim" not in created.public_dict()

def test_existing_sqlite_sync_table_migrates_optional_report_columns(tmp_path):
 path=tmp_path/"legacy.db"
 with sqlite3.connect(path) as connection:
  connection.execute("CREATE TABLE ads_sync_runs (sync_id TEXT PRIMARY KEY,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT,mode TEXT NOT NULL,start_date TEXT NOT NULL,end_date TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,status TEXT NOT NULL,success INTEGER NOT NULL,campaigns_fetched INTEGER NOT NULL,ad_groups_fetched INTEGER NOT NULL,keywords_fetched INTEGER NOT NULL,targets_fetched INTEGER NOT NULL,report_rows_received INTEGER NOT NULL,rows_normalized INTEGER NOT NULL,rows_saved INTEGER NOT NULL,rows_failed INTEGER NOT NULL,error_code TEXT,error_summary TEXT,created_at TEXT NOT NULL,trigger_source TEXT NOT NULL DEFAULT 'manual')")
  connection.execute("INSERT INTO ads_sync_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",("old","s","m","p",HISTORICAL_SYNC_MODE,"2026-02-08","2026-02-09",NOW.isoformat(),None,"running",0,0,0,0,0,0,0,0,0,None,None,NOW.isoformat(),"manual"))
 repo=AdsPerformanceRepository(path);repo.initialize();old=repo.active_sync_run("s","m","p")
 assert old.sync_id=="old" and old.report_id is None and old.amazon_report_status is None
 with sqlite3.connect(path) as connection:columns={row[1] for row in connection.execute("PRAGMA table_info(ads_sync_runs)")}
 assert {"report_id","report_type_id","amazon_report_status","report_created_at","report_last_checked_at","report_claim"}<=columns
