from datetime import date,datetime,timezone
import sqlite3
from app.amazon_ads.sync_models import AdsManualSyncResult
from app.database.ads_repository import AdsPerformanceRepository
NOW=datetime(2026,2,10,tzinfo=timezone.utc)
def run(identifier,trigger="manual",profile="p"):return AdsManualSyncResult(identifier,"historical_campaign_report","s","m",profile,date(2026,2,8),date(2026,2,9),NOW,NOW,True,"completed",trigger_source=trigger)
def test_trigger_source_round_trip_and_scheduled_cadence_filter(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");repo.save_sync_run(run("manual","manual"));repo.save_sync_run(run("scheduled","scheduled"));rows=repo.list_sync_runs("s","m","p");assert {item.trigger_source for item in rows}=={"manual","scheduled"} and repo.latest_successful_sync("s","m","p","historical_campaign_report","scheduled").sync_id=="scheduled"
def test_existing_database_migration_backfills_manual_safely(tmp_path):
 path=tmp_path/"old.db";connection=sqlite3.connect(path);connection.execute("CREATE TABLE ads_sync_runs (sync_id TEXT PRIMARY KEY,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT,mode TEXT NOT NULL,start_date TEXT NOT NULL,end_date TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,status TEXT NOT NULL,success INTEGER NOT NULL,campaigns_fetched INTEGER NOT NULL,ad_groups_fetched INTEGER NOT NULL,keywords_fetched INTEGER NOT NULL,targets_fetched INTEGER NOT NULL,report_rows_received INTEGER NOT NULL,rows_normalized INTEGER NOT NULL,rows_saved INTEGER NOT NULL,rows_failed INTEGER NOT NULL,error_code TEXT,error_summary TEXT,created_at TEXT NOT NULL)");connection.commit();connection.close();repo=AdsPerformanceRepository(path);repo.initialize()
 assert "trigger_source" in {row[1] for row in sqlite3.connect(path).execute("PRAGMA table_info(ads_sync_runs)")}
