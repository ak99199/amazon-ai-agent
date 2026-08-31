"""Bounded, read-only Ads ingestion orchestration."""
from datetime import date,datetime,timezone
from uuid import uuid4
from app.amazon_ads.ingestion_models import AdsIngestionResult
class AdsIngestionService:
    def __init__(self,campaigns,keywords,search_terms,repository,now=None):self._campaigns=campaigns;self._keywords=keywords;self._search_terms=search_terms;self._repository=repository;self._now=now or (lambda:datetime.now(timezone.utc))
    def run(self,seller_id,marketplace_id,profile_id,start_date,end_date,report_source,max_campaign_pages=10,max_keyword_pages=10,max_report_rows=10000,today=None):
        today=today or self._now().date();self._validate_dates(start_date,end_date,today);self._validate_bounds(max_campaign_pages,max_keyword_pages,max_report_rows);started=self._now();run_id=str(uuid4());counts={"campaigns":0,"keywords":0,"targets":0,"received":0,"normalized":0,"saved":0,"failed":0};errors=[];success=True
        try:
            campaigns=self._campaigns.list_campaigns(profile_id,max_campaign_pages);keywords=self._keywords.list_keywords(profile_id,max_keyword_pages);targets=self._keywords.list_targets(profile_id,max_keyword_pages);rows=report_source.list_search_terms(profile_id,start_date,end_date,max_report_rows)
            counts.update(campaigns=len(campaigns),keywords=len(keywords),targets=len(targets));rows=rows[:max_report_rows];counts["received"]=len(rows)
            for raw in rows:
                try:
                    normalized=self._search_terms.normalize_row(seller_id,marketplace_id,profile_id,raw);counts["normalized"]+=1;self._repository.save(normalized);counts["saved"]+=1
                except Exception as error:counts["failed"]+=1;errors.append("report row normalization failed")
        except Exception as error:success=False;errors.append("Ads ingestion source failed")
        result=AdsIngestionResult(run_id,started,self._now(),counts["campaigns"],counts["keywords"],counts["targets"],counts["received"],counts["normalized"],counts["saved"],counts["failed"],success,tuple(errors));self._repository.save_ingestion_run(result,seller_id,marketplace_id,profile_id);return result
    @staticmethod
    def _validate_dates(start,end,today):
        if start>end or end>today or (end-start).days>89:raise ValueError("Ads ingestion date range is invalid")
    @staticmethod
    def _validate_bounds(campaign_pages,keyword_pages,report_rows):
        if not 1<=campaign_pages<=100 or not 1<=keyword_pages<=100 or not 1<=report_rows<=10000:raise ValueError("Ads ingestion limits are invalid")