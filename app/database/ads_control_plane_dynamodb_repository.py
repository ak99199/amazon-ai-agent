"""Injected-table DynamoDB foundation for scoped Ads control-plane records."""
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from app.amazon_ads.action_models import AdsRecommendationDecision
from app.amazon_ads.execution_models import AdsExecutionPlan
from app.amazon_ads.write_intent_models import AdsWriteIntent
from app.amazon_ads.write_command_models import AdsSealedWriteCommand
from app.amazon_ads.rule_tuning_models import AdsRuleTuningProposal


class AdsControlPlaneRepositoryError(RuntimeError):pass


def _safe(value):
    if isinstance(value,datetime):return value.isoformat()
    if isinstance(value,Decimal):return value
    if isinstance(value,tuple):return [_safe(v) for v in value]
    if isinstance(value,list):return [_safe(v) for v in value]
    if isinstance(value,dict):return {str(k):_safe(v) for k,v in value.items()}
    return value


class DynamoDbAdsControlPlaneRepository:
    def __init__(self,table,client,table_name=None):
        if table is None or client is None:raise AdsControlPlaneRepositoryError("Injected DynamoDB table and client are required")
        self.table=table;self.client=client;self.table_name=table_name or getattr(table,"name",None)
    @staticmethod
    def scope_key(seller,marketplace,profile):return f"SELLER#{seller}#MARKETPLACE#{marketplace}#PROFILE#{profile}"
    def _item(self,prefix,identifier,obj):
        value=_safe(asdict(obj));value.update({"PK":self.scope_key(obj.seller_id,obj.marketplace_id,obj.profile_id),"SK":f"{prefix}#{identifier}","record_type":prefix});return value
    def _transaction(self,items):
        try:self.client.transact_write_items(TransactItems=items)
        except Exception as error:raise AdsControlPlaneRepositoryError("Ads control-plane transaction failed") from error
    @staticmethod
    def _decision(v):return AdsRecommendationDecision(v["recommendation_id"],v["seller_id"],v["marketplace_id"],v["profile_id"],v["scope_type"],v["scope_id"],v["recommendation_code"],v["recommendation_title"],v["status"],v.get("review_note"),v.get("review_source","dashboard"),v.get("decision_id"),datetime.fromisoformat(v["created_at"]) if v.get("created_at") else None,datetime.fromisoformat(v["updated_at"]) if v.get("updated_at") else None,datetime.fromisoformat(v["reviewed_at"]) if v.get("reviewed_at") else None,v.get("recommendation_snapshot"))
    @staticmethod
    def _plan(v):return AdsExecutionPlan(v["recommendation_id"],v.get("decision_id"),v["seller_id"],v["marketplace_id"],v["profile_id"],v["scope_type"],v["scope_id"],v["recommendation_code"],v["action_type"],v.get("direction","none"),v.get("current_value"),v.get("proposed_value"),bool(v.get("dry_run",True)),bool(v.get("eligible",False)),v.get("status","error"),v.get("eligibility_code","error"),v.get("eligibility_reason",""),tuple(v.get("safety_checks",[])),datetime.fromisoformat(v["created_at"]) if v.get("created_at") else None,v.get("execution_plan_id"))
    def get_decision(self,seller,marketplace,profile,recommendation_id):
        value=self._get(seller,marketplace,profile,f"DECISION#{recommendation_id}");return self._decision(value) if value else None
    def list_decisions(self,seller,marketplace,profile,status=None,limit=200):
        values=[self._decision(v) for v in self._query(seller,marketplace,profile,"DECISION#",200)]
        return sorted((v for v in values if status is None or v.status==status),key=lambda v:v.updated_at or v.created_at,reverse=True)[:limit]
    def save_decision(self,decision):
        existing=self.get_decision(decision.seller_id,decision.marketplace_id,decision.profile_id,decision.recommendation_id)
        if existing and existing.status==decision.status and existing.review_note==decision.review_note:return existing
        record=self._item("DECISION",decision.recommendation_id,decision);event_id=f"{decision.stable_decision_id}#{decision.status}#{getattr(decision,'updated_at',None)}";event={"PK":record["PK"],"SK":f"DECISION_EVENT#{decision.recommendation_id}#{event_id}","decision_id":decision.stable_decision_id,"recommendation_id":decision.recommendation_id,"old_status":getattr(existing,"status",None),"new_status":decision.status,"created_at":decision.updated_at.isoformat() if decision.updated_at else decision.created_at.isoformat()}
        put={"TableName":self.table_name,"Item":record,"ConditionExpression":"#status=:old" if existing else "attribute_not_exists(PK) AND attribute_not_exists(SK)","ExpressionAttributeNames":{"#status":"status"},"ExpressionAttributeValues":{":old":existing.status if existing else ""}}
        self._transaction([{"Put":put},{"Put":{"TableName":self.table_name,"Item":event,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}]);return decision
    def list_decision_events(self,seller,marketplace,profile,recommendation_id):return self._query(seller,marketplace,profile,f"DECISION_EVENT#{recommendation_id}#",200,True)
    def get_execution_plan(self,seller,marketplace,profile,plan_hash):
        value=self._get(seller,marketplace,profile,f"EXECUTION_PLAN#{plan_hash}");return self._plan(value) if value else None
    def list_execution_plans(self,seller,marketplace,profile,limit=50):return sorted((self._plan(v) for v in self._query(seller,marketplace,profile,"EXECUTION_PLAN#",200)),key=lambda v:v.created_at,reverse=True)[:limit]
    def save_execution_plan(self,plan):
        existing=self.get_execution_plan(plan.seller_id,plan.marketplace_id,plan.profile_id,plan.plan_hash)
        if existing and existing.status==plan.status and existing.eligible==plan.eligible and existing.safety_checks==plan.safety_checks:return existing
        record=self._item("EXECUTION_PLAN",plan.plan_hash,plan);event={"PK":record["PK"],"SK":f"EXECUTION_EVENT#{plan.stable_execution_plan_id}#{plan.status}#{plan.created_at.isoformat()}","execution_plan_id":plan.stable_execution_plan_id,"event_type":"PLAN_ELIGIBLE" if plan.eligible else "PLAN_REJECTED","created_at":plan.created_at.isoformat()}
        put={"TableName":self.table_name,"Item":record,"ConditionExpression":"#status=:old" if existing else "attribute_not_exists(PK) AND attribute_not_exists(SK)","ExpressionAttributeNames":{"#status":"status"},"ExpressionAttributeValues":{":old":existing.status if existing else ""}}
        self._transaction([{"Put":put},{"Put":{"TableName":self.table_name,"Item":event,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}]);return plan
    def list_execution_events(self,seller,marketplace,profile,identifier):return self._query(seller,marketplace,profile,f"EXECUTION_EVENT#{identifier}#",200,True)
    def create_rule_version(self,rule_version_id,seller_id=None,marketplace_id=None,profile_id=None,version_name=None,status=None,thresholds=None,source=None,created_by=None,notes=None,created_at=None,source_proposal_id=None,activated_at=None):
        if not isinstance(rule_version_id,str):
            v=rule_version_id;rule_version_id=v.rule_version_id;seller_id=v.seller_id;marketplace_id=v.marketplace_id;profile_id=v.profile_id;version_name=v.version_name;status=v.status;thresholds=v.thresholds;source=v.source;created_by=v.created_by;notes=v.notes;created_at=v.created_at;source_proposal_id=getattr(v,"source_proposal_id",None);activated_at=getattr(v,"activated_at",None)
        if status not in ("active","proposed","rejected","archived"):raise ValueError("Invalid rule-version status")
        created_at=created_at or datetime.now().astimezone();item={"PK":self.scope_key(seller_id,marketplace_id,str(profile_id)),"SK":f"RULE_VERSION#{rule_version_id}","rule_version_id":rule_version_id,"seller_id":seller_id,"marketplace_id":marketplace_id,"profile_id":str(profile_id),"version_name":version_name,"status":status,"thresholds":_safe(thresholds),"source":source,"source_proposal_id":source_proposal_id,"created_by":created_by,"notes":notes,"created_at":created_at.isoformat(),"updated_at":created_at.isoformat(),"activated_at":activated_at.isoformat() if activated_at else None}
        self._transaction([{"Put":{"TableName":self.table_name,"Item":_safe(item),"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}]);return item
    def get_rule_version(self,seller,marketplace,profile,identifier):return self._get(seller,marketplace,profile,f"RULE_VERSION#{identifier}")
    def list_rule_versions(self,seller,marketplace,profile,limit=100):return sorted(self._query(seller,marketplace,profile,"RULE_VERSION#",200),key=lambda v:v.get("created_at",""),reverse=True)[:limit]
    def get_active_rule_version(self,seller,marketplace,profile):return next((v for v in self.list_rule_versions(seller,marketplace,profile,200) if v.get("status")=="active"),None)
    def update_rule_version_status(self,seller,marketplace,profile,identifier,status,updated_at=None,activated_at=None):
        if status not in ("active","proposed","rejected","archived"):raise ValueError("Invalid rule-version status")
        current=self.get_rule_version(seller,marketplace,profile,identifier)
        if not current:return None
        current=dict(current);current["status"]=status;current["updated_at"]=(updated_at or datetime.now().astimezone()).isoformat();current["activated_at"]=activated_at.isoformat() if activated_at else current.get("activated_at")
        self._transaction([{"Put":{"TableName":self.table_name,"Item":_safe(current)}}]);return current
    def save_rule_tuning_proposal(self,proposal):
        record=self._item("RULE_TUNING",proposal.proposal_id,proposal);event={"PK":record["PK"],"SK":f"RULE_TUNING_EVENT#{proposal.proposal_id}#CREATED","proposal_id":proposal.proposal_id,"event_type":"PROPOSAL_CREATED","created_at":proposal.created_at.isoformat()}
        if self._get(proposal.seller_id,proposal.marketplace_id,proposal.profile_id,record["SK"]):return proposal
        self._transaction([{"Put":{"TableName":self.table_name,"Item":record,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}},{"Put":{"TableName":self.table_name,"Item":event,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}]);return proposal
    def get_rule_tuning_proposal(self,seller,marketplace,profile,identifier):return self._get(seller,marketplace,profile,f"RULE_TUNING#{identifier}")
    def list_rule_tuning_proposals(self,seller,marketplace,profile,limit=100):return sorted(self._query(seller,marketplace,profile,"RULE_TUNING#",200),key=lambda v:v.get("created_at",""),reverse=True)[:limit]
    def review_rule_tuning_proposal(self,seller,marketplace,profile,identifier,status,reviewed_at):
        if status not in ("approved_for_future_rule_version","rejected","dismissed"):raise ValueError("Invalid rule-tuning decision")
        current=self.get_rule_tuning_proposal(seller,marketplace,profile,identifier)
        if not current:return None
        current=dict(current);current.update({"status":status,"updated_at":reviewed_at.isoformat(),"reviewed_at":reviewed_at.isoformat()});event={"PK":current["PK"],"SK":f"RULE_TUNING_EVENT#{identifier}#{status}","proposal_id":identifier,"event_type":{"approved_for_future_rule_version":"PROPOSAL_APPROVED","rejected":"PROPOSAL_REJECTED","dismissed":"PROPOSAL_DISMISSED"}[status],"created_at":reviewed_at.isoformat()}
        self._transaction([{"Put":{"TableName":self.table_name,"Item":current,"ConditionExpression":"#status=:old","ExpressionAttributeNames":{"#status":"status"},"ExpressionAttributeValues":{":old":self.get_rule_tuning_proposal(seller,marketplace,profile,identifier)["status"]}}},{"Put":{"TableName":self.table_name,"Item":event,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}]);return status
    def insert_rule_activation_event(self,event_id,seller,marketplace,profile,event_type,from_id,to_id,created_at,source_proposal_id=None):
        item={"PK":self.scope_key(seller,marketplace,str(profile)),"SK":f"RULE_ACTIVATION_EVENT#{created_at.isoformat()}#{event_id}","event_id":event_id,"event_type":event_type,"from_rule_version_id":from_id,"to_rule_version_id":to_id,"source_proposal_id":source_proposal_id,"created_at":created_at.isoformat()};self._transaction([{"Put":{"TableName":self.table_name,"Item":_safe(item),"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}]);return item
    def list_rule_activation_events(self,seller,marketplace,profile,limit=100):return self._query(seller,marketplace,profile,"RULE_ACTIVATION_EVENT#",limit)
    def get_latest_rule_activation_event(self,seller,marketplace,profile):
        values=self.list_rule_activation_events(seller,marketplace,profile,1);return values[0] if values else None
    def activate_rule_version(self,seller,marketplace,profile,target_id,expected_id,event_id,activated_at):
        current=self.get_active_rule_version(seller,marketplace,profile);target=self.get_rule_version(seller,marketplace,profile,target_id)
        if (current.get("rule_version_id") if current else None)!=expected_id or not target or target.get("status")!="proposed":return None
        pk=self.scope_key(seller,marketplace,str(profile));items=[]
        if current:items.append({"Update":{"TableName":self.table_name,"Key":{"PK":pk,"SK":f"RULE_VERSION#{expected_id}"},"UpdateExpression":"SET #s=:archived,updated_at=:at","ConditionExpression":"#s=:active","ExpressionAttributeNames":{"#s":"status"},"ExpressionAttributeValues":{":archived":"archived",":active":"active",":at":activated_at.isoformat()}}})
        items.append({"Update":{"TableName":self.table_name,"Key":{"PK":pk,"SK":f"RULE_VERSION#{target_id}"},"UpdateExpression":"SET #s=:active,updated_at=:at,activated_at=:at","ConditionExpression":"#s=:proposed","ExpressionAttributeNames":{"#s":"status"},"ExpressionAttributeValues":{":active":"active",":proposed":"proposed",":at":activated_at.isoformat()}}})
        event={"PK":pk,"SK":f"RULE_ACTIVATION_EVENT#{activated_at.isoformat()}#{event_id}","event_id":event_id,"event_type":"RULE_VERSION_ACTIVATED","from_rule_version_id":expected_id,"to_rule_version_id":target_id,"source_proposal_id":target.get("source_proposal_id"),"created_at":activated_at.isoformat()};items.append({"Put":{"TableName":self.table_name,"Item":_safe(event),"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}});self._transaction(items);return {"previous_rule_version_id":expected_id,"target":{**target,"status":"active","updated_at":activated_at.isoformat(),"activated_at":activated_at.isoformat()}}
    def get_rollback_candidate(self,seller,marketplace,profile,current_rule_version_id=None):
        current=self.get_active_rule_version(seller,marketplace,profile)
        if not current or (current_rule_version_id is not None and current.get("rule_version_id")!=current_rule_version_id):return None
        event=next((e for e in self.list_rule_activation_events(seller,marketplace,profile,200) if e.get("event_type")=="RULE_VERSION_ACTIVATED" and e.get("to_rule_version_id")==current.get("rule_version_id")),None)
        if not event or not event.get("from_rule_version_id"):return None
        return self.get_rule_version(seller,marketplace,profile,event["from_rule_version_id"]) or {"rule_version_id":event["from_rule_version_id"],"status":"missing","thresholds":None}
    def rollback_rule_version(self,seller,marketplace,profile,expected_id,event_id,rolled_back_at):
        current=self.get_active_rule_version(seller,marketplace,profile)
        if (current.get("rule_version_id") if current else None)!=expected_id:return {"status":"conflict"}
        if not current:return {"status":"blocked"}
        previous=self.get_rollback_candidate(seller,marketplace,profile,expected_id)
        if not previous or previous.get("status")!="archived":return {"status":"no_history" if previous is None else "blocked"}
        pk=self.scope_key(seller,marketplace,str(profile));previous_id=previous["rule_version_id"];at=rolled_back_at.isoformat();event={"PK":pk,"SK":f"RULE_ACTIVATION_EVENT#{at}#{event_id}","event_id":event_id,"event_type":"RULE_VERSION_ROLLED_BACK","from_rule_version_id":expected_id,"to_rule_version_id":previous_id,"source_proposal_id":previous.get("source_proposal_id"),"created_at":at}
        self._transaction([{"Update":{"TableName":self.table_name,"Key":{"PK":pk,"SK":f"RULE_VERSION#{expected_id}"},"UpdateExpression":"SET #s=:archived,updated_at=:at","ConditionExpression":"#s=:active","ExpressionAttributeNames":{"#s":"status"},"ExpressionAttributeValues":{":archived":"archived",":active":"active",":at":at}}},{"Update":{"TableName":self.table_name,"Key":{"PK":pk,"SK":f"RULE_VERSION#{previous_id}"},"UpdateExpression":"SET #s=:active,updated_at=:at,activated_at=:at","ConditionExpression":"#s=:archived","ExpressionAttributeNames":{"#s":"status"},"ExpressionAttributeValues":{":active":"active",":archived":"archived",":at":at}}},{"Put":{"TableName":self.table_name,"Item":_safe(event),"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}]);return {"status":"rolled_back","from_rule_version_id":expected_id,"to_rule_version_id":previous_id}
    def save_write_intent(self,intent):
        record=self._item("WRITE_INTENT",intent.write_intent_id,intent);event={"PK":record["PK"],"SK":f"WRITE_INTENT_EVENT#{intent.write_intent_id}#PREPARED","event_type":"WRITE_INTENT_PREPARED","write_intent_id":intent.write_intent_id,"created_at":intent.created_at.isoformat()}
        existing=self._get(intent.seller_id,intent.marketplace_id,intent.profile_id,record["SK"])
        if existing:
            if existing.get("idempotency_key")==intent.idempotency_key:return intent
            raise AdsControlPlaneRepositoryError("Immutable write intent conflict")
        try:self._transaction([{"Put":{"TableName":self.table_name,"Item":record,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}},{"Put":{"TableName":self.table_name,"Item":event,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}])
        except AdsControlPlaneRepositoryError:
            existing=self._get(intent.seller_id,intent.marketplace_id,intent.profile_id,record["SK"])
            if not existing or existing.get("idempotency_key")!=intent.idempotency_key:raise
        return intent
    def transition_write_intent(self,seller,marketplace,profile,identifier,new_status,event_type,created_at):
        pk=self.scope_key(seller,marketplace,str(profile));event={"PK":pk,"SK":f"WRITE_INTENT_EVENT#{identifier}#{event_type}","event_type":event_type,"write_intent_id":identifier,"old_status":"prepared","new_status":new_status,"created_at":created_at.isoformat()}
        self._transaction([{"Update":{"TableName":self.table_name,"Key":{"PK":pk,"SK":f"WRITE_INTENT#{identifier}"},"UpdateExpression":"SET #status=:new","ConditionExpression":"#status=:prepared","ExpressionAttributeNames":{"#status":"status"},"ExpressionAttributeValues":{":new":new_status,":prepared":"prepared"}}},{"Put":{"TableName":self.table_name,"Item":event,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}]);return self.get_write_intent(seller,marketplace,profile,identifier)
    def save_sealed_write_command(self,command):
        record=self._item("SEALED_COMMAND",command.command_id,command);event={"PK":record["PK"],"SK":f"SEALED_COMMAND_EVENT#{command.command_id}#SEALED","event_type":"WRITE_COMMAND_SEALED","command_id":command.command_id,"created_at":command.created_at.isoformat()}
        existing=self._get(command.seller_id,command.marketplace_id,command.profile_id,record["SK"])
        if existing:
            if existing.get("command_hash")==command.command_hash:return command
            raise AdsControlPlaneRepositoryError("Immutable sealed command conflict")
        try:self._transaction([{"Put":{"TableName":self.table_name,"Item":record,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}},{"Put":{"TableName":self.table_name,"Item":event,"ConditionExpression":"attribute_not_exists(PK) AND attribute_not_exists(SK)"}}])
        except AdsControlPlaneRepositoryError:
            existing=self._get(command.seller_id,command.marketplace_id,command.profile_id,record["SK"])
            if not existing or existing.get("command_hash")!=command.command_hash:raise
        return command
    def _get(self,seller,marketplace,profile,sort_key):
        try:return self.table.get_item(Key={"PK":self.scope_key(seller,marketplace,str(profile)),"SK":sort_key},ConsistentRead=True).get("Item")
        except Exception as error:raise AdsControlPlaneRepositoryError("Ads control-plane read failed") from error
    def _query(self,seller,marketplace,profile,prefix,limit=200,forward=False):
        try:return self.table.query(KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",ExpressionAttributeValues={":pk":self.scope_key(seller,marketplace,str(profile)),":prefix":prefix},ScanIndexForward=forward,Limit=max(1,min(limit,200))).get("Items",[])
        except Exception as error:raise AdsControlPlaneRepositoryError("Ads control-plane query failed") from error
    @staticmethod
    def _intent(v):return AdsWriteIntent(v["write_intent_id"],v["idempotency_key"],v["execution_plan_id"],v["recommendation_id"],v["decision_id"],v["proposal_id"],v["preflight_id"],v["seller_id"],v["marketplace_id"],v["profile_id"],v["scope_type"],v["scope_id"],v["recommendation_code"],v["action_type"],v["direction"],str(v["current_value"]),str(v["proposed_value"]),v.get("currency"),v["status"],datetime.fromisoformat(v["created_at"]),v.get("source","controlled_preflight"),int(v.get("schema_version",1)))
    @staticmethod
    def _command(v):return AdsSealedWriteCommand(v["command_id"],v["command_hash"],v["write_intent_id"],v["target_resolution_id"],v["execution_plan_id"],v["recommendation_id"],v["decision_id"],v["proposal_id"],v["preflight_id"],v["seller_id"],v["marketplace_id"],v["profile_id"],v["ad_product"],v["advertiser_entity_type"],v["advertiser_entity_id"],v.get("campaign_id"),v.get("ad_group_id"),v["action_type"],v["mutation_kind"],v["direction"],str(v["expected_current_value"]),str(v["proposed_value"]),v.get("currency"),v["status"],datetime.fromisoformat(v["created_at"]),int(v.get("schema_version",1)),v.get("source","sealed_internal_command"))
    def get_write_intent(self,seller,marketplace,profile,identifier):
        value=self._get(seller,marketplace,profile,f"WRITE_INTENT#{identifier}");return self._intent(value) if value else None
    def list_write_intents(self,seller,marketplace,profile,status=None,limit=50):
        values=[self._intent(v) for v in self._query(seller,marketplace,profile,"WRITE_INTENT#",200)]
        return sorted((v for v in values if status is None or v.status==status),key=lambda v:v.created_at,reverse=True)[:limit]
    def list_write_intent_events(self,seller,marketplace,profile,identifier):return self._query(seller,marketplace,profile,f"WRITE_INTENT_EVENT#{identifier}#",200,True)
    def list_sealed_write_commands(self,seller,marketplace,profile,status=None,limit=50):
        values=[self._command(v) for v in self._query(seller,marketplace,profile,"SEALED_COMMAND#",200)]
        return sorted((v for v in values if status is None or v.status==status),key=lambda v:v.created_at,reverse=True)[:limit]
    def list_sealed_write_command_events(self,seller,marketplace,profile,identifier):return self._query(seller,marketplace,profile,f"SEALED_COMMAND_EVENT#{identifier}#",200,True)
