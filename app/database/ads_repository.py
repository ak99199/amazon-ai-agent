"""Seller-scoped SQLite repository for normalized Ads data and human decisions."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import uuid

from app.amazon_ads.action_models import AdsRecommendationDecision
from app.amazon_ads.execution_models import AdsExecutionPlan
import json
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.database.connection import DATABASE_PATH, get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ads_performance_daily (id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT NOT NULL,date TEXT NOT NULL,ad_product TEXT NOT NULL,campaign_id TEXT,campaign_name TEXT,ad_group_id TEXT,ad_group_name TEXT,keyword_id TEXT,keyword_text TEXT,match_type TEXT,target_id TEXT,target_expression TEXT,search_term TEXT,currency TEXT,impressions INTEGER NOT NULL,clicks INTEGER NOT NULL,spend TEXT NOT NULL,orders_count INTEGER NOT NULL,units INTEGER NOT NULL,sales TEXT NOT NULL,dimension_key TEXT NOT NULL,UNIQUE(seller_id,marketplace_id,profile_id,date,ad_product,dimension_key));
CREATE INDEX IF NOT EXISTS idx_ads_profile_date ON ads_performance_daily(profile_id,date);
CREATE INDEX IF NOT EXISTS idx_ads_campaign_date ON ads_performance_daily(campaign_id,date);
CREATE INDEX IF NOT EXISTS idx_ads_keyword_date ON ads_performance_daily(keyword_id,date);
CREATE INDEX IF NOT EXISTS idx_ads_search_term_date ON ads_performance_daily(search_term,date);
CREATE TABLE IF NOT EXISTS ads_ingestion_runs (run_id TEXT PRIMARY KEY,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT NOT NULL,success INTEGER NOT NULL,campaigns_fetched INTEGER NOT NULL,keywords_fetched INTEGER NOT NULL,targets_fetched INTEGER NOT NULL,report_rows_received INTEGER NOT NULL,rows_normalized INTEGER NOT NULL,rows_saved INTEGER NOT NULL,rows_failed INTEGER NOT NULL,error_summary TEXT);
CREATE INDEX IF NOT EXISTS idx_ads_runs_scope_started ON ads_ingestion_runs(seller_id,marketplace_id,profile_id,started_at DESC);
CREATE TABLE IF NOT EXISTS ads_recommendation_decisions (decision_id TEXT PRIMARY KEY,recommendation_id TEXT NOT NULL,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT NOT NULL,scope_type TEXT NOT NULL,scope_id TEXT NOT NULL,recommendation_code TEXT NOT NULL,recommendation_title TEXT NOT NULL,status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','dismissed')),review_note TEXT,review_source TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,reviewed_at TEXT,UNIQUE(seller_id,marketplace_id,profile_id,recommendation_id));
CREATE INDEX IF NOT EXISTS idx_ads_decisions_scope_status ON ads_recommendation_decisions(seller_id,marketplace_id,profile_id,status);
CREATE INDEX IF NOT EXISTS idx_ads_decisions_recommendation ON ads_recommendation_decisions(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_ads_decisions_updated ON ads_recommendation_decisions(updated_at DESC);
CREATE TABLE IF NOT EXISTS ads_recommendation_decision_events (event_id TEXT PRIMARY KEY,decision_id TEXT NOT NULL,recommendation_id TEXT NOT NULL,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT NOT NULL,old_status TEXT,new_status TEXT NOT NULL,review_note TEXT,review_source TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_ads_decision_events_scope ON ads_recommendation_decision_events(seller_id,marketplace_id,profile_id,created_at DESC);CREATE TABLE IF NOT EXISTS ads_execution_plans (execution_plan_id TEXT PRIMARY KEY,recommendation_id TEXT NOT NULL,decision_id TEXT,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT NOT NULL,scope_type TEXT NOT NULL,scope_id TEXT NOT NULL,recommendation_code TEXT NOT NULL,action_type TEXT NOT NULL,direction TEXT NOT NULL,dry_run INTEGER NOT NULL CHECK (dry_run=1),eligible INTEGER NOT NULL,status TEXT NOT NULL,eligibility_code TEXT NOT NULL,eligibility_reason TEXT NOT NULL,safety_checks TEXT NOT NULL,plan_hash TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(seller_id,marketplace_id,profile_id,plan_hash));
CREATE INDEX IF NOT EXISTS idx_ads_execution_plans_scope_created ON ads_execution_plans(seller_id,marketplace_id,profile_id,created_at DESC);
CREATE TABLE IF NOT EXISTS ads_execution_events (event_id TEXT PRIMARY KEY,execution_plan_id TEXT NOT NULL,recommendation_id TEXT NOT NULL,seller_id TEXT NOT NULL,marketplace_id TEXT NOT NULL,profile_id TEXT NOT NULL,event_type TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_ads_execution_events_scope ON ads_execution_events(seller_id,marketplace_id,profile_id,created_at DESC);
"""


class AdsPerformanceRepository:
    def __init__(self, database_path: Path | str = DATABASE_PATH):
        self._database_path = database_path

    def initialize(self):
        with get_connection(self._database_path) as connection:
            connection.executescript(_SCHEMA)

    def save(self, row):
        self.initialize()
        columns = ("seller_id","marketplace_id","profile_id","date","ad_product","campaign_id","campaign_name","ad_group_id","ad_group_name","keyword_id","keyword_text","match_type","target_id","target_expression","search_term","currency","impressions","clicks","spend","orders_count","units","sales","dimension_key")
        values = (row.seller_id,row.marketplace_id,row.profile_id,row.date.isoformat(),row.ad_product,row.campaign_id,row.campaign_name,row.ad_group_id,row.ad_group_name,row.keyword_id,row.keyword_text,row.match_type,row.target_id,row.target_expression,row.search_term,row.currency,row.impressions,row.clicks,str(row.spend),row.orders,row.units,str(row.sales),row.dimension_key)
        updates = ",".join(f"{name}=excluded.{name}" for name in columns if name not in ("seller_id","marketplace_id","profile_id","date","ad_product","dimension_key"))
        with get_connection(self._database_path) as connection:
            connection.execute(f"INSERT INTO ads_performance_daily ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) ON CONFLICT(seller_id,marketplace_id,profile_id,date,ad_product,dimension_key) DO UPDATE SET {updates}", values)
        return row

    def save_many(self, rows):
        return [self.save(row) for row in rows]

    def save_ingestion_run(self, result, seller_id, marketplace_id, profile_id):
        self.initialize()
        values=(result.run_id,seller_id,marketplace_id,str(profile_id),result.started_at.isoformat(),result.finished_at.isoformat(),int(result.success),result.campaigns_fetched,result.keywords_fetched,result.targets_fetched,result.report_rows_received,result.rows_normalized,result.rows_saved,result.rows_failed,"; ".join(result.errors) or None)
        with get_connection(self._database_path) as connection:
            connection.execute("INSERT INTO ads_ingestion_runs (run_id,seller_id,marketplace_id,profile_id,started_at,finished_at,success,campaigns_fetched,keywords_fetched,targets_fetched,report_rows_received,rows_normalized,rows_saved,rows_failed,error_summary) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)

    def list_ingestion_runs(self, seller_id, marketplace_id, profile_id, limit=30):
        self.initialize()
        with get_connection(self._database_path) as connection:
            return connection.execute("SELECT * FROM ads_ingestion_runs WHERE seller_id=? AND marketplace_id=? AND profile_id=? ORDER BY started_at DESC LIMIT ?", (seller_id,marketplace_id,str(profile_id),max(1,min(limit,100)))).fetchall()

    def count_performance_rows(self, seller_id, marketplace_id, profile_id):
        self.initialize()
        with get_connection(self._database_path) as connection:
            return connection.execute("SELECT COUNT(*) FROM ads_performance_daily WHERE seller_id=? AND marketplace_id=? AND profile_id=?", (seller_id,marketplace_id,str(profile_id))).fetchone()[0]

    def get_data_date_range(self, seller_id, marketplace_id, profile_id):
        self.initialize()
        with get_connection(self._database_path) as connection:
            return connection.execute("SELECT MIN(date),MAX(date) FROM ads_performance_daily WHERE seller_id=? AND marketplace_id=? AND profile_id=?", (seller_id,marketplace_id,str(profile_id))).fetchone()

    def count_ingestion_runs(self, seller_id, marketplace_id, profile_id, success=None):
        self.initialize()
        clause = "" if success is None else " AND success=?"
        values = (seller_id,marketplace_id,str(profile_id)) if success is None else (seller_id,marketplace_id,str(profile_id),int(success))
        with get_connection(self._database_path) as connection:
            return connection.execute("SELECT COUNT(*) FROM ads_ingestion_runs WHERE seller_id=? AND marketplace_id=? AND profile_id=?" + clause, values).fetchone()[0]

    def get_latest_ingestion_run(self, seller_id, marketplace_id, profile_id):
        rows = self.list_ingestion_runs(seller_id,marketplace_id,profile_id,1)
        return rows[0] if rows else None

    def get_latest_successful_ingestion_run(self, seller_id, marketplace_id, profile_id):
        self.initialize()
        with get_connection(self._database_path) as connection:
            return connection.execute("SELECT * FROM ads_ingestion_runs WHERE seller_id=? AND marketplace_id=? AND profile_id=? AND success=1 ORDER BY started_at DESC LIMIT 1", (seller_id,marketplace_id,str(profile_id))).fetchone()

    def list_rows(self, seller_id, marketplace_id, profile_id, start_date, end_date, campaign_id=None, keyword_id=None, search_term=None, today=None):
        today = today or date.today()
        if start_date > end_date or end_date > today:
            raise ValueError("Ads query date range is invalid")
        self.initialize(); clauses=["seller_id=?","marketplace_id=?","profile_id=?","date>=?","date<=?"]; values=[seller_id,marketplace_id,str(profile_id),start_date.isoformat(),end_date.isoformat()]
        for column, value in (("campaign_id",campaign_id),("keyword_id",keyword_id),("search_term",search_term)):
            if value is not None:
                clauses.append(f"{column}=?"); values.append(value)
        with get_connection(self._database_path) as connection:
            rows=connection.execute(f"SELECT * FROM ads_performance_daily WHERE {' AND '.join(clauses)} ORDER BY date,campaign_id", values).fetchall()
        return [self._row(item) for item in rows]

    def list_window(self, seller_id, marketplace_id, profile_id, days, reference_date=None, **filters):
        if days not in (7,14,30,60,90):
            raise ValueError("Unsupported Ads query window")
        reference_date=reference_date or date.today()
        return self.list_rows(seller_id,marketplace_id,profile_id,reference_date-timedelta(days=days-1),reference_date,today=reference_date,**filters)

    def get_decision(self, seller_id, marketplace_id, profile_id, recommendation_id):
        self.initialize()
        with get_connection(self._database_path) as connection:
            row=connection.execute("SELECT * FROM ads_recommendation_decisions WHERE seller_id=? AND marketplace_id=? AND profile_id=? AND recommendation_id=?", (seller_id,marketplace_id,str(profile_id),recommendation_id)).fetchone()
        return self._decision(row) if row else None

    def list_decisions(self, seller_id, marketplace_id, profile_id, status=None, limit=200):
        self.initialize(); clauses=["seller_id=?","marketplace_id=?","profile_id=?"]; values=[seller_id,marketplace_id,str(profile_id)]
        if status is not None:
            clauses.append("status=?"); values.append(status)
        with get_connection(self._database_path) as connection:
            rows=connection.execute(f"SELECT * FROM ads_recommendation_decisions WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?", (*values,max(1,min(limit,200)))).fetchall()
        return [self._decision(row) for row in rows]

    def save_decision(self, decision):
        self.initialize()
        existing=self.get_decision(decision.seller_id,decision.marketplace_id,decision.profile_id,decision.recommendation_id)
        if existing and existing.status == decision.status and existing.review_note == decision.review_note:
            return existing
        current=decision if not existing else AdsRecommendationDecision(decision.recommendation_id,decision.seller_id,decision.marketplace_id,decision.profile_id,decision.scope_type,decision.scope_id,decision.recommendation_code,decision.recommendation_title,decision.status,decision.review_note,decision.review_source,existing.stable_decision_id,existing.created_at,decision.updated_at,decision.reviewed_at)
        values=(current.stable_decision_id,current.recommendation_id,current.seller_id,current.marketplace_id,current.profile_id,current.scope_type,current.scope_id,current.recommendation_code,current.recommendation_title,current.status,current.review_note,current.review_source,current.created_at.isoformat(),current.updated_at.isoformat(),current.reviewed_at.isoformat() if current.reviewed_at else None)
        with get_connection(self._database_path) as connection:
            connection.execute("INSERT INTO ads_recommendation_decisions(decision_id,recommendation_id,seller_id,marketplace_id,profile_id,scope_type,scope_id,recommendation_code,recommendation_title,status,review_note,review_source,created_at,updated_at,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(seller_id,marketplace_id,profile_id,recommendation_id) DO UPDATE SET status=excluded.status,review_note=excluded.review_note,review_source=excluded.review_source,updated_at=excluded.updated_at,reviewed_at=excluded.reviewed_at",values)
            connection.execute("INSERT INTO ads_recommendation_decision_events(event_id,decision_id,recommendation_id,seller_id,marketplace_id,profile_id,old_status,new_status,review_note,review_source,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),current.stable_decision_id,current.recommendation_id,current.seller_id,current.marketplace_id,current.profile_id,existing.status if existing else None,current.status,current.review_note,current.review_source,current.updated_at.isoformat()))
        return current

    def list_decision_events(self, seller_id, marketplace_id, profile_id, recommendation_id):
        self.initialize()
        with get_connection(self._database_path) as connection:
            return connection.execute("SELECT * FROM ads_recommendation_decision_events WHERE seller_id=? AND marketplace_id=? AND profile_id=? AND recommendation_id=? ORDER BY created_at", (seller_id,marketplace_id,str(profile_id),recommendation_id)).fetchall()

    def get_execution_plan(self,seller_id,marketplace_id,profile_id,plan_hash):
        self.initialize()
        with get_connection(self._database_path) as connection:row=connection.execute("SELECT * FROM ads_execution_plans WHERE seller_id=? AND marketplace_id=? AND profile_id=? AND plan_hash=?",(seller_id,marketplace_id,str(profile_id),plan_hash)).fetchone()
        return self._execution_plan(row) if row else None
    def list_execution_plans(self,seller_id,marketplace_id,profile_id,limit=50):
        self.initialize()
        with get_connection(self._database_path) as connection:rows=connection.execute("SELECT * FROM ads_execution_plans WHERE seller_id=? AND marketplace_id=? AND profile_id=? ORDER BY created_at DESC LIMIT ?",(seller_id,marketplace_id,str(profile_id),max(1,min(limit,200)))).fetchall()
        return [self._execution_plan(row) for row in rows]
    def save_execution_plan(self,plan):
        self.initialize();existing=self.get_execution_plan(plan.seller_id,plan.marketplace_id,plan.profile_id,plan.plan_hash)
        if existing and existing.status==plan.status and existing.eligible==plan.eligible and existing.safety_checks==plan.safety_checks:return existing
        values=(plan.stable_execution_plan_id,plan.recommendation_id,plan.decision_id,plan.seller_id,plan.marketplace_id,plan.profile_id,plan.scope_type,plan.scope_id,plan.recommendation_code,plan.action_type,plan.direction,1,int(plan.eligible),plan.status,plan.eligibility_code,plan.eligibility_reason,json.dumps(list(plan.safety_checks),sort_keys=True,separators=(",",":")),plan.plan_hash,plan.created_at.isoformat())
        with get_connection(self._database_path) as connection:
            connection.execute("INSERT INTO ads_execution_plans(execution_plan_id,recommendation_id,decision_id,seller_id,marketplace_id,profile_id,scope_type,scope_id,recommendation_code,action_type,direction,dry_run,eligible,status,eligibility_code,eligibility_reason,safety_checks,plan_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(seller_id,marketplace_id,profile_id,plan_hash) DO UPDATE SET decision_id=excluded.decision_id,eligible=excluded.eligible,status=excluded.status,eligibility_code=excluded.eligibility_code,eligibility_reason=excluded.eligibility_reason,safety_checks=excluded.safety_checks,created_at=excluded.created_at",values)
            connection.execute("INSERT INTO ads_execution_events(event_id,execution_plan_id,recommendation_id,seller_id,marketplace_id,profile_id,event_type,message,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),plan.stable_execution_plan_id,plan.recommendation_id,plan.seller_id,plan.marketplace_id,plan.profile_id,"PLAN_ELIGIBLE" if plan.eligible else "PLAN_REJECTED",plan.eligibility_reason,plan.created_at.isoformat()))
        return plan
    def list_execution_events(self,seller_id,marketplace_id,profile_id,execution_plan_id):
        self.initialize()
        with get_connection(self._database_path) as connection:return connection.execute("SELECT * FROM ads_execution_events WHERE seller_id=? AND marketplace_id=? AND profile_id=? AND execution_plan_id=? ORDER BY created_at",(seller_id,marketplace_id,str(profile_id),execution_plan_id)).fetchall()
    @staticmethod
    def _execution_plan(item):
        checks=tuple(json.loads(item["safety_checks"]))
        return AdsExecutionPlan(item["recommendation_id"],item["decision_id"],item["seller_id"],item["marketplace_id"],item["profile_id"],item["scope_type"],item["scope_id"],item["recommendation_code"],item["action_type"],item["direction"],None,None,True,bool(item["eligible"]),item["status"],item["eligibility_code"],item["eligibility_reason"],checks,datetime.fromisoformat(item["created_at"]),item["execution_plan_id"])
    @staticmethod
    def _decision(item):
        return AdsRecommendationDecision(item["recommendation_id"],item["seller_id"],item["marketplace_id"],item["profile_id"],item["scope_type"],item["scope_id"],item["recommendation_code"],item["recommendation_title"],item["status"],item["review_note"],item["review_source"],item["decision_id"],datetime.fromisoformat(item["created_at"]),datetime.fromisoformat(item["updated_at"]),datetime.fromisoformat(item["reviewed_at"]) if item["reviewed_at"] else None)

    @staticmethod
    def _row(item):
        return AdsPerformanceDaily(item["seller_id"],item["marketplace_id"],item["profile_id"],date.fromisoformat(item["date"]),item["ad_product"],item["campaign_id"],item["campaign_name"],item["ad_group_id"],item["ad_group_name"],item["keyword_id"],item["keyword_text"],item["match_type"],item["target_id"],item["target_expression"],item["search_term"],item["currency"],item["impressions"],item["clicks"],Decimal(item["spend"]),item["orders_count"],item["units"],Decimal(item["sales"]))