"""Read-only, scope-isolated historical Ads sync health."""
from datetime import datetime,time,timedelta,timezone
from os import getenv
from app.amazon_ads.sync_models import AdsHistoricalSyncHealth
from app.services.ads_manual_historical_sync_service import HISTORICAL_SYNC_MODE

class AdsHistoricalSyncHealthService:
 def __init__(self,repository,gate_service,now=None,stale_after_hours=None):self.repository=repository;self.gate=gate_service;self.now=now or (lambda:datetime.now(timezone.utc));self.stale_hours=max(24,int(stale_after_hours if stale_after_hours is not None else getenv("AMAZON_ADS_HISTORICAL_SYNC_STALE_AFTER_HOURS","72")))
 def get(self,seller_id,marketplace_id,profile_id=None,limit=10):
  now=self.now();profile_id=profile_id or self.gate.settings.profile_id;runs=self.repository.list_sync_runs(seller_id,marketplace_id,profile_id,max(1,min(limit,20)),HISTORICAL_SYNC_MODE);latest=runs[0] if runs else None;success=self.repository.latest_successful_sync(seller_id,marketplace_id,profile_id,HISTORICAL_SYNC_MODE);active=bool(self.repository.active_sync_run(seller_id,marketplace_id,profile_id));start=now.date()-timedelta(days=2);end=now.date()-timedelta(days=1);gate=self.gate.evaluate(seller_id,marketplace_id,profile_id,start,end);last_date=self.repository.latest_campaign_performance_date(seller_id,marketplace_id,profile_id)
  age=max(0,int((now-datetime.combine(last_date+timedelta(days=1),time.min,tzinfo=timezone.utc)).total_seconds())) if last_date else None;freshness="unknown" if last_date is None else "fresh" if age<=self.stale_hours*3600 else "stale";successes=sum(item.success for item in runs);failures=sum(not item.success and item.status=="failed" for item in runs)
  if active:overall="running"
  elif not runs:overall="no_sync_yet"
  elif latest and not latest.success and not success:overall="failed"
  elif latest and not latest.success:overall="degraded"
  elif gate.cooldown_active:overall="cooldown"
  elif freshness=="stale":overall="stale"
  else:overall="healthy"
  latest_success=self.repository.latest_successful_sync(seller_id,marketplace_id,profile_id);remaining=0
  if gate.cooldown_active and latest_success:
   anchor=latest_success.finished_at or latest_success.started_at;remaining=max(0,self.gate.cooldown_seconds-int((now-anchor).total_seconds()))
  safe=lambda item:{"run_id":item.sync_id,"started_at":item.started_at.isoformat(),"completed_at":item.finished_at.isoformat() if item.finished_at else None,"status":item.status,"rows_persisted":item.rows_saved,"error_code":item.error_code}
  return AdsHistoricalSyncHealth(overall,latest.status if latest else None,latest.started_at.isoformat() if latest else None,latest.finished_at.isoformat() if latest and latest.finished_at else None,(success.finished_at or success.started_at).isoformat() if success else None,success.rows_saved if success else None,active,gate.cooldown_active,remaining,freshness,age,last_date.isoformat() if last_date else None,successes,failures,tuple(safe(item) for item in runs),tuple([gate.status_message] if not gate.allowed and not active and not gate.cooldown_active else []))
