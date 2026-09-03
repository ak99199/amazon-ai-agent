"""Injected-table DynamoDB foundation for scoped Ads control-plane records."""
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal


class AdsControlPlaneRepositoryError(RuntimeError):pass


def _safe(value):
    if isinstance(value,datetime):return value.isoformat()
    if isinstance(value,Decimal):return value
    if isinstance(value,tuple):return [_safe(v) for v in value]
    if isinstance(value,list):return [_safe(v) for v in value]
    if isinstance(value,dict):return {str(k):_safe(v) for k,v in value.items() if v is not None}
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
    def get_write_intent(self,seller,marketplace,profile,identifier):return self._get(seller,marketplace,profile,f"WRITE_INTENT#{identifier}")
