"""Dedicated DynamoDB repository for historical Amazon Ads data only."""
from datetime import date,datetime
from decimal import Decimal
from app.amazon_ads.sync_models import AdsManualSyncResult

class AdsDynamoDbRepositoryError(RuntimeError):pass

def _scope(seller,marketplace,profile):
    parts=(str(seller),str(marketplace),str(profile))
    return "SCOPE#"+"#".join(f"{len(value)}:{value}" for value in parts)
def _av(value):
    if value is None:return {"NULL":True}
    if isinstance(value,bool):return {"BOOL":value}
    if isinstance(value,(int,Decimal)):return {"N":str(value)}
    return {"S":str(value)}
def _encoded(item):return {key:_av(value) for key,value in item.items()}

class DynamoDbAdsHistoricalRepository:
    def __init__(self,performance_table,sync_runs_table,client=None):
        self.performance_table=performance_table;self.sync_runs_table=sync_runs_table
        self.client=client or sync_runs_table.meta.client
        self.performance_table_name=getattr(performance_table,"name",None) or getattr(performance_table,"table_name")
        self.sync_runs_table_name=getattr(sync_runs_table,"name",None) or getattr(sync_runs_table,"table_name")
    @staticmethod
    def scope_key(seller,marketplace,profile):return _scope(seller,marketplace,profile)
    @staticmethod
    def performance_key(row):return f"PERF#{row.date.isoformat()}#{row.ad_product}#{row.dimension_key}"
    @staticmethod
    def run_key(run):return f"RUN#{run.started_at.isoformat()}#{run.sync_id}"
    @staticmethod
    def _performance_item(row):
        return {"scope_key":_scope(row.seller_id,row.marketplace_id,row.profile_id),"performance_key":DynamoDbAdsHistoricalRepository.performance_key(row),"seller_id":row.seller_id,"marketplace_id":row.marketplace_id,"profile_id":str(row.profile_id),"date":row.date.isoformat(),"ad_product":row.ad_product,"campaign_id":row.campaign_id,"campaign_name":row.campaign_name,"ad_group_id":row.ad_group_id,"ad_group_name":row.ad_group_name,"keyword_id":row.keyword_id,"keyword_text":row.keyword_text,"match_type":row.match_type,"target_id":row.target_id,"target_expression":row.target_expression,"search_term":row.search_term,"currency":row.currency,"impressions":int(row.impressions),"clicks":int(row.clicks),"spend":Decimal(row.spend),"orders":int(row.orders),"units":int(row.units),"sales":Decimal(row.sales),"dimension_key":row.dimension_key,"grain_type":"campaign" if row.campaign_id and not any((row.keyword_id,row.target_id,row.search_term)) else "detail"}
    @staticmethod
    def _run_item(run,key=None):
        return {"scope_key":_scope(run.seller_id,run.marketplace_id,run.profile_id),"run_key":key or DynamoDbAdsHistoricalRepository.run_key(run),"sync_id":run.sync_id,"seller_id":run.seller_id,"marketplace_id":run.marketplace_id,"profile_id":str(run.profile_id),"mode":run.mode,"start_date":run.start_date.isoformat(),"end_date":run.end_date.isoformat(),"started_at":run.started_at.isoformat(),"finished_at":run.finished_at.isoformat() if run.finished_at else None,"success":bool(run.success),"status":run.status,"campaigns_fetched":int(run.campaigns_fetched),"ad_groups_fetched":int(run.ad_groups_fetched),"keywords_fetched":int(run.keywords_fetched),"targets_fetched":int(run.targets_fetched),"report_rows_received":int(run.report_rows_received),"rows_normalized":int(run.rows_normalized),"rows_saved":int(run.rows_saved),"rows_failed":int(run.rows_failed),"error_code":run.error_code,"error_summary":run.safe_error_message,"trigger_source":run.trigger_source}
    @staticmethod
    def _run(item):
        return AdsManualSyncResult(item["sync_id"],item["mode"],item["seller_id"],item["marketplace_id"],item.get("profile_id"),date.fromisoformat(item["start_date"]),date.fromisoformat(item["end_date"]),datetime.fromisoformat(item["started_at"]),datetime.fromisoformat(item["finished_at"]) if item.get("finished_at") else None,bool(item.get("success")),item["status"],int(item.get("campaigns_fetched",0)),int(item.get("ad_groups_fetched",0)),int(item.get("keywords_fetched",0)),int(item.get("targets_fetched",0)),int(item.get("report_rows_received",0)),int(item.get("rows_normalized",0)),int(item.get("rows_saved",0)),int(item.get("rows_failed",0)),item.get("error_code"),item.get("error_summary"),item.get("trigger_source","manual"))
    def _transact(self,items):
        try:self.client.transact_write_items(TransactItems=items)
        except Exception as error:raise AdsDynamoDbRepositoryError("Amazon Ads persistent storage operation failed.") from None
    @staticmethod
    def _conditional_failure(error):
        response=getattr(error,"response",{}) or {};code=response.get("Error",{}).get("Code")
        if code=="ConditionalCheckFailedException":return True
        if code!="TransactionCanceledException":return type(error).__name__ in ("ConditionalCheckFailedException","TransactionCanceledException")
        reasons=response.get("CancellationReasons") or []
        return bool(reasons) and all(reason.get("Code") in (None,"None","ConditionalCheckFailed") for reason in reasons) and any(reason.get("Code")=="ConditionalCheckFailed" for reason in reasons)
    def save_many(self,rows):
        rows=list(rows)
        if not rows:return []
        if len(rows)>100:raise AdsDynamoDbRepositoryError("Amazon Ads performance batch exceeds the supported limit.")
        if any(not Decimal(row.spend).is_finite() or not Decimal(row.sales).is_finite() for row in rows):raise AdsDynamoDbRepositoryError("Amazon Ads performance batch contains invalid numeric values.")
        items=[self._performance_item(row) for row in rows];keys={(item["scope_key"],item["performance_key"]) for item in items}
        if len(keys)!=len(items):raise AdsDynamoDbRepositoryError("Amazon Ads performance batch contains duplicate logical rows.")
        self._transact([{"Put":{"TableName":self.performance_table_name,"Item":_encoded(item)}} for item in items]);return rows
    def start_sync_run_if_idle(self,run,not_before):
        del not_before
        item=self._run_item(run);lock={**item,"run_key":"LOCK","history_run_key":item["run_key"]}
        transaction=[{"Put":{"TableName":self.sync_runs_table_name,"Item":_encoded(item),"ConditionExpression":"attribute_not_exists(scope_key) AND attribute_not_exists(run_key)"}},{"Put":{"TableName":self.sync_runs_table_name,"Item":_encoded(lock),"ConditionExpression":"attribute_not_exists(scope_key) AND attribute_not_exists(run_key)"}}]
        try:self.client.transact_write_items(TransactItems=transaction);return True
        except Exception as error:
            if self._conditional_failure(error):return False
            raise AdsDynamoDbRepositoryError("Amazon Ads persistent storage operation failed.") from None
    def active_sync_run(self,seller,marketplace,profile):
        try:item=self.sync_runs_table.get_item(Key={"scope_key":_scope(seller,marketplace,profile),"run_key":"LOCK"},ConsistentRead=True).get("Item")
        except Exception:raise AdsDynamoDbRepositoryError("Amazon Ads persistent storage read failed.") from None
        return self._run(item) if item else None
    def has_active_sync(self,seller,marketplace,profile,not_before):
        active=self.active_sync_run(seller,marketplace,profile);return bool(active and active.started_at>=not_before)
    @staticmethod
    def _summary_keys(run,failed=False):
        kind="FAILED" if failed else "SUCCESS";mode=run.mode;source=run.trigger_source
        return (f"SUMMARY#{kind}#ANY",f"SUMMARY#{kind}#MODE#{mode}",f"SUMMARY#{kind}#SOURCE#{source}",f"SUMMARY#{kind}#MODE#{mode}#SOURCE#{source}")
    def _summary_puts(self,run,failed=False):
        item=self._run_item(run);result=[]
        for key in self._summary_keys(run,failed):
            summary={**item,"run_key":key,"history_run_key":self.run_key(run)}
            result.append({"Put":{"TableName":self.sync_runs_table_name,"Item":_encoded(summary),"ConditionExpression":"attribute_not_exists(started_at) OR started_at <= :started","ExpressionAttributeValues":{":started":_av(run.started_at.isoformat())}}})
        return result
    def save_sync_run(self,run):
        if run.status in ("starting","running"):
            self._transact([{"Put":{"TableName":self.sync_runs_table_name,"Item":_encoded(self._run_item(run)),"ConditionExpression":"attribute_not_exists(scope_key) AND attribute_not_exists(run_key)"}}]);return run
        scope=_scope(run.seller_id,run.marketplace_id,run.profile_id);key=self.run_key(run);item=self._run_item(run)
        transaction=[{"Put":{"TableName":self.sync_runs_table_name,"Item":_encoded(item),"ConditionExpression":"#status IN (:running,:starting)","ExpressionAttributeNames":{"#status":"status"},"ExpressionAttributeValues":{":running":_av("running"),":starting":_av("starting")}}},{"Delete":{"TableName":self.sync_runs_table_name,"Key":_encoded({"scope_key":scope,"run_key":"LOCK"}),"ConditionExpression":"sync_id = :sync","ExpressionAttributeValues":{":sync":_av(run.sync_id)}}},*self._summary_puts(run,failed=not run.success)]
        self._transact(transaction);return run
    def finalize_stale_sync_run(self,run_id,seller,marketplace,profile,cutoff,finished_at):
        active=self.active_sync_run(seller,marketplace,profile)
        if not active or active.sync_id!=run_id or active.status!="running" or active.started_at>cutoff:return False
        failed=AdsManualSyncResult(active.sync_id,active.mode,active.seller_id,active.marketplace_id,active.profile_id,active.start_date,active.end_date,active.started_at,finished_at,False,"failed",active.campaigns_fetched,active.ad_groups_fetched,active.keywords_fetched,active.targets_fetched,active.report_rows_received,active.rows_normalized,active.rows_saved,active.rows_failed,"stale_run_timeout","Previous Ads sync exceeded the allowed running window and was finalized as failed.",active.trigger_source)
        scope=_scope(seller,marketplace,profile);item=self._run_item(failed)
        transaction=[{"Put":{"TableName":self.sync_runs_table_name,"Item":_encoded(item),"ConditionExpression":"#status = :running AND started_at <= :cutoff","ExpressionAttributeNames":{"#status":"status"},"ExpressionAttributeValues":{":running":_av("running"),":cutoff":_av(cutoff.isoformat())}}},{"Delete":{"TableName":self.sync_runs_table_name,"Key":_encoded({"scope_key":scope,"run_key":"LOCK"}),"ConditionExpression":"sync_id = :sync AND started_at <= :cutoff","ExpressionAttributeValues":{":sync":_av(run_id),":cutoff":_av(cutoff.isoformat())}}},*self._summary_puts(failed,failed=True)]
        try:self.client.transact_write_items(TransactItems=transaction);return True
        except Exception as error:
            if self._conditional_failure(error):return False
            raise AdsDynamoDbRepositoryError("Amazon Ads persistent storage operation failed.") from None
    def _query_runs(self,seller,marketplace,profile):
        values={":scope":_scope(seller,marketplace,profile),":prefix":"RUN#"};items=[];start=None
        while len(items)<1000:
            args={"KeyConditionExpression":"scope_key = :scope AND begins_with(run_key, :prefix)","ExpressionAttributeValues":values,"ScanIndexForward":False,"ConsistentRead":True}
            if start:args["ExclusiveStartKey"]=start
            try:response=self.sync_runs_table.query(**args)
            except Exception:raise AdsDynamoDbRepositoryError("Amazon Ads persistent storage query failed.") from None
            items.extend(response.get("Items",[]));start=response.get("LastEvaluatedKey")
            if not start:break
        return items[:1000]
    def list_sync_runs(self,seller,marketplace,profile,limit=20,mode=None):
        result=[]
        for item in self._query_runs(seller,marketplace,profile):
            if mode is None or item.get("mode")==mode:result.append(self._run(item))
            if len(result)>=max(1,min(limit,100)):break
        return result
    def latest_sync_run(self,seller,marketplace,profile):
        try:response=self.sync_runs_table.query(KeyConditionExpression="scope_key = :scope AND begins_with(run_key, :prefix)",ExpressionAttributeValues={":scope":_scope(seller,marketplace,profile),":prefix":"RUN#"},ScanIndexForward=False,ConsistentRead=True,Limit=1)
        except Exception:raise AdsDynamoDbRepositoryError("Amazon Ads persistent storage query failed.") from None
        items=response.get("Items",[]);return self._run(items[0]).public_dict() if items else None
    @staticmethod
    def _summary_key(failed,mode,source):
        kind="FAILED" if failed else "SUCCESS"
        if mode and source:return f"SUMMARY#{kind}#MODE#{mode}#SOURCE#{source}"
        if mode:return f"SUMMARY#{kind}#MODE#{mode}"
        if source:return f"SUMMARY#{kind}#SOURCE#{source}"
        return f"SUMMARY#{kind}#ANY"
    def _latest(self,seller,marketplace,profile,failed,mode=None,trigger_source=None):
        key={"scope_key":_scope(seller,marketplace,profile),"run_key":self._summary_key(failed,mode,trigger_source)}
        try:item=self.sync_runs_table.get_item(Key=key,ConsistentRead=True).get("Item")
        except Exception:raise AdsDynamoDbRepositoryError("Amazon Ads persistent storage read failed.") from None
        return self._run(item) if item else None
    def latest_successful_sync(self,seller,marketplace,profile,mode=None,trigger_source=None):return self._latest(seller,marketplace,profile,False,mode,trigger_source)
    def latest_failed_sync(self,seller,marketplace,profile,mode=None,trigger_source=None):return self._latest(seller,marketplace,profile,True,mode,trigger_source)
    def latest_campaign_performance_date(self,seller,marketplace,profile):
        values={":scope":_scope(seller,marketplace,profile),":prefix":"PERF#"};start=None;pages=0
        while pages<10:
            args={"KeyConditionExpression":"scope_key = :scope AND begins_with(performance_key, :prefix)","ExpressionAttributeValues":values,"ScanIndexForward":False,"ConsistentRead":True,"Limit":100}
            if start:args["ExclusiveStartKey"]=start
            try:response=self.performance_table.query(**args)
            except Exception:raise AdsDynamoDbRepositoryError("Amazon Ads persistent storage query failed.") from None
            for item in response.get("Items",[]):
                if item.get("ad_product")=="SP" and item.get("grain_type")=="campaign":return date.fromisoformat(item["date"])
            start=response.get("LastEvaluatedKey");pages+=1
            if not start:break
        return None
    def count_sync_runs_since(self,seller,marketplace,profile,since):return sum(run.started_at>=since for run in self.list_sync_runs(seller,marketplace,profile,100))
    def aggregate_sync_counts_since(self,seller,marketplace,profile,since):
        runs=[run for run in self.list_sync_runs(seller,marketplace,profile,100) if run.started_at>=since];return sum(run.rows_saved for run in runs),sum(run.rows_failed for run in runs)
