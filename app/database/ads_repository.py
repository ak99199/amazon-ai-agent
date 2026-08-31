"""Seller-scoped SQLite repository for normalized Ads performance and ingestion history."""
from datetime import date,timedelta
from pathlib import Path
from decimal import Decimal
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.database.connection import DATABASE_PATH,get_connection
_SCHEMA="""
CREATE TABLE IF NOT EXISTS ads_performance_daily (id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT NOT NULL,date TEXT NOT NULL,ad_product TEXT NOT NULL,campaign_id TEXT,campaign_name TEXT,ad_group_id TEXT,ad_group_name TEXT,keyword_id TEXT,keyword_text TEXT,match_type TEXT,target_id TEXT,target_expression TEXT,search_term TEXT,currency TEXT,impressions INTEGER NOT NULL,clicks INTEGER NOT NULL,spend TEXT NOT NULL,orders_count INTEGER NOT NULL,units INTEGER NOT NULL,sales TEXT NOT NULL,dimension_key TEXT NOT NULL,UNIQUE(seller_id,marketplace_id,profile_id,date,ad_product,dimension_key));
CREATE INDEX IF NOT EXISTS idx_ads_profile_date ON ads_performance_daily(profile_id,date);
CREATE INDEX IF NOT EXISTS idx_ads_campaign_date ON ads_performance_daily(campaign_id,date);
CREATE INDEX IF NOT EXISTS idx_ads_keyword_date ON ads_performance_daily(keyword_id,date);
CREATE INDEX IF NOT EXISTS idx_ads_search_term_date ON ads_performance_daily(search_term,date);
CREATE TABLE IF NOT EXISTS ads_ingestion_runs (run_id TEXT PRIMARY KEY,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT NOT NULL,success INTEGER NOT NULL,campaigns_fetched INTEGER NOT NULL,keywords_fetched INTEGER NOT NULL,targets_fetched INTEGER NOT NULL,report_rows_received INTEGER NOT NULL,rows_normalized INTEGER NOT NULL,rows_saved INTEGER NOT NULL,rows_failed INTEGER NOT NULL,error_summary TEXT);
CREATE INDEX IF NOT EXISTS idx_ads_runs_scope_started ON ads_ingestion_runs(seller_id,marketplace_id,profile_id,started_at DESC);
"""
class AdsPerformanceRepository:
    def __init__(self,database_path:Path|str=DATABASE_PATH):self._database_path=database_path
    def initialize(self):
        with get_connection(self._database_path) as connection:connection.executescript(_SCHEMA)
    def save(self,row):
        self.initialize();columns=("seller_id","marketplace_id","profile_id","date","ad_product","campaign_id","campaign_name","ad_group_id","ad_group_name","keyword_id","keyword_text","match_type","target_id","target_expression","search_term","currency","impressions","clicks","spend","orders_count","units","sales","dimension_key");values=(row.seller_id,row.marketplace_id,row.profile_id,row.date.isoformat(),row.ad_product,row.campaign_id,row.campaign_name,row.ad_group_id,row.ad_group_name,row.keyword_id,row.keyword_text,row.match_type,row.target_id,row.target_expression,row.search_term,row.currency,row.impressions,row.clicks,str(row.spend),row.orders,row.units,str(row.sales),row.dimension_key);updates=",".join(f"{name}=excluded.{name}" for name in columns if name not in ("seller_id","marketplace_id","profile_id","date","ad_product","dimension_key"))
        with get_connection(self._database_path) as connection:connection.execute(f"INSERT INTO ads_performance_daily ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) ON CONFLICT(seller_id,marketplace_id,profile_id,date,ad_product,dimension_key) DO UPDATE SET {updates}",values)
        return row
    def save_many(self,rows):return [self.save(row) for row in rows]
    def save_ingestion_run(self,result,seller_id,marketplace_id,profile_id):
        self.initialize();values=(result.run_id,seller_id,marketplace_id,str(profile_id),result.started_at.isoformat(),result.finished_at.isoformat(),int(result.success),result.campaigns_fetched,result.keywords_fetched,result.targets_fetched,result.report_rows_received,result.rows_normalized,result.rows_saved,result.rows_failed,"; ".join(result.errors) or None)
        with get_connection(self._database_path) as connection:connection.execute("INSERT INTO ads_ingestion_runs (run_id,seller_id,marketplace_id,profile_id,started_at,finished_at,success,campaigns_fetched,keywords_fetched,targets_fetched,report_rows_received,rows_normalized,rows_saved,rows_failed,error_summary) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",values)
    def list_ingestion_runs(self,seller_id,marketplace_id,profile_id,limit=30):
        self.initialize()
        with get_connection(self._database_path) as connection:return connection.execute("SELECT * FROM ads_ingestion_runs WHERE seller_id=? AND marketplace_id=? AND profile_id=? ORDER BY started_at DESC LIMIT ?",(seller_id,marketplace_id,str(profile_id),max(1,min(limit,100)))).fetchall()
    def list_rows(self,seller_id,marketplace_id,profile_id,start_date,end_date,campaign_id=None,keyword_id=None,search_term=None,today=None):
        today=today or date.today()
        if start_date>end_date or end_date>today:raise ValueError("Ads query date range is invalid")
        self.initialize();clauses=["seller_id=?","marketplace_id=?","profile_id=?","date>=?","date<=?"];values=[seller_id,marketplace_id,str(profile_id),start_date.isoformat(),end_date.isoformat()]
        for column,value in (("campaign_id",campaign_id),("keyword_id",keyword_id),("search_term",search_term)):
            if value is not None:clauses.append(f"{column}=?");values.append(value)
        with get_connection(self._database_path) as connection:rows=connection.execute(f"SELECT * FROM ads_performance_daily WHERE {' AND '.join(clauses)} ORDER BY date,campaign_id",values).fetchall()
        return [self._row(item) for item in rows]
    def list_window(self,seller_id,marketplace_id,profile_id,days,reference_date=None,**filters):
        if days not in (7,14,30,60,90):raise ValueError("Unsupported Ads query window")
        reference_date=reference_date or date.today();return self.list_rows(seller_id,marketplace_id,profile_id,reference_date-timedelta(days=days-1),reference_date,today=reference_date,**filters)
    @staticmethod
    def _row(item):return AdsPerformanceDaily(item["seller_id"],item["marketplace_id"],item["profile_id"],date.fromisoformat(item["date"]),item["ad_product"],item["campaign_id"],item["campaign_name"],item["ad_group_id"],item["ad_group_name"],item["keyword_id"],item["keyword_text"],item["match_type"],item["target_id"],item["target_expression"],item["search_term"],item["currency"],item["impressions"],item["clicks"],Decimal(item["spend"]),item["orders_count"],item["units"],Decimal(item["sales"]))