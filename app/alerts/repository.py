"""SQLite and DynamoDB repositories for internal seller alerts."""
from datetime import datetime
from os import getenv
from pathlib import Path
from uuid import uuid4
from app.alerts.models import Alert
from app.database.connection import DATABASE_PATH, get_connection
class AlertStorageConfigurationError(Exception): pass
class SQLiteAlertRepository:
    def __init__(self,database_path:Path|str=DATABASE_PATH): self._database_path=database_path
    def save(self,alert):
        with get_connection(self._database_path) as connection: connection.execute("INSERT INTO alerts (alert_id,seller_id,marketplace_id,asin,alert_type,severity,title,message,action_code,created_at,dedupe_key,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(alert.alert_id,alert.seller_id,alert.marketplace_id,alert.asin,alert.alert_type,alert.severity,alert.title,alert.message,alert.action_code,alert.created_at.isoformat(),alert.dedupe_key,alert.status))
        return alert
    def get_by_dedupe_key(self,seller_id,marketplace_id,dedupe_key):
        rows=self._query("SELECT * FROM alerts WHERE seller_id=? AND marketplace_id=? AND dedupe_key=? LIMIT 1",(seller_id,marketplace_id,dedupe_key)); return rows[0] if rows else None
    def list_alerts(self,seller_id,marketplace_id,status=None,severity=None,limit=50):
        clauses=["seller_id=?","marketplace_id=?"];values=[seller_id,marketplace_id]
        if status: clauses.append("status=?");values.append(status)
        if severity: clauses.append("severity=?");values.append(severity)
        values.append(max(1,min(limit,200)));return self._query(f"SELECT * FROM alerts WHERE {' AND '.join(clauses)} ORDER BY created_at DESC,alert_id DESC LIMIT ?",tuple(values))
    def count_alerts(self,seller_id,marketplace_id,status=None):
        clauses=["seller_id=?","marketplace_id=?"];values=[seller_id,marketplace_id]
        if status: clauses.append("status=?");values.append(status)
        with get_connection(self._database_path) as connection: return connection.execute(f"SELECT COUNT(*) FROM alerts WHERE {' AND '.join(clauses)}",tuple(values)).fetchone()[0]
    def dismiss(self,seller_id,marketplace_id,alert_id): return self._set_status(seller_id,marketplace_id,alert_id,"dismissed")
    def mark_sent(self,seller_id,marketplace_id,alert_id): return self._set_status(seller_id,marketplace_id,alert_id,"sent",only_new=True)
    def _set_status(self,seller_id,marketplace_id,alert_id,status,only_new=False):
        suffix=" AND status='new'" if only_new else ""
        with get_connection(self._database_path) as connection: result=connection.execute(f"UPDATE alerts SET status=? WHERE seller_id=? AND marketplace_id=? AND alert_id=?{suffix}",(status,seller_id,marketplace_id,alert_id))
        return result.rowcount==1
    def _query(self,query,values):
        with get_connection(self._database_path) as connection: rows=connection.execute(query,values).fetchall()
        return [Alert(row["alert_id"],row["seller_id"],row["marketplace_id"],row["asin"],row["alert_type"],row["severity"],row["title"],row["message"],row["action_code"],datetime.fromisoformat(row["created_at"]),row["dedupe_key"],row["status"]) for row in rows]
class DynamoDbAlertRepository:
    """DynamoDB alerts table: seller_marketplace (PK), created_at_alert_id (SK)."""
    def __init__(self,table): self._table=table
    def save(self,alert): self._table.put_item(Item={**alert.public_dict(),"seller_marketplace":f"{alert.seller_id}#{alert.marketplace_id}","created_at_alert_id":f"{alert.created_at.isoformat()}#{alert.alert_id}"});return alert
    def get_by_dedupe_key(self,seller_id,marketplace_id,dedupe_key):
        matches=[item for item in self._items(seller_id,marketplace_id) if item.get("dedupe_key")==dedupe_key];return self._to_alert(matches[0]) if matches else None
    def list_alerts(self,seller_id,marketplace_id,status=None,severity=None,limit=50):
        items=[item for item in self._items(seller_id,marketplace_id) if (not status or item.get("status")==status) and (not severity or item.get("severity")==severity)];return [self._to_alert(item) for item in sorted(items,key=lambda x:(x.get("created_at",""),x.get("alert_id","")),reverse=True)[:max(1,min(limit,200))]]
    def count_alerts(self,seller_id,marketplace_id,status=None): return len(self.list_alerts(seller_id,marketplace_id,status=status,limit=200))
    def dismiss(self,seller_id,marketplace_id,alert_id): return self._set_status(seller_id,marketplace_id,alert_id,"dismissed")
    def mark_sent(self,seller_id,marketplace_id,alert_id): return self._set_status(seller_id,marketplace_id,alert_id,"sent")
    def _items(self,seller_id,marketplace_id): return [item for item in self._table.scan().get("Items",[]) if item.get("seller_marketplace")==f"{seller_id}#{marketplace_id}"]
    def _set_status(self,seller_id,marketplace_id,alert_id,status):
        item=next((item for item in self._items(seller_id,marketplace_id) if item.get("alert_id")==alert_id),None)
        if not item:return False
        self._table.update_item(Key={"seller_marketplace":f"{seller_id}#{marketplace_id}","created_at_alert_id":item["created_at_alert_id"]},UpdateExpression="SET #status = :status",ExpressionAttributeNames={"#status":"status"},ExpressionAttributeValues={":status":status});return True
    @staticmethod
    def _to_alert(item): return Alert(item["alert_id"],item["seller_id"],item["marketplace_id"],item["asin"],item["alert_type"],item["severity"],item["title"],item["message"],item["action_code"],datetime.fromisoformat(item["created_at"]),item["dedupe_key"],item.get("status","new"))
def create_alert_repository(backend=None):
    mode=backend or getenv("STORAGE_BACKEND","sqlite")
    if mode=="sqlite":return SQLiteAlertRepository()
    if mode!="dynamodb":raise AlertStorageConfigurationError("Alert storage is not configured")
    table_name=getenv("DYNAMODB_ALERTS_TABLE")
    if not table_name:raise AlertStorageConfigurationError("Alert storage is not configured")
    try:import boto3
    except ImportError as error:raise AlertStorageConfigurationError("DynamoDB support is unavailable") from error
    return DynamoDbAlertRepository(boto3.resource("dynamodb").Table(table_name))
def new_alert_id():return str(uuid4())