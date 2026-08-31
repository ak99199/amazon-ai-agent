"""DynamoDB-backed seller-isolated snapshot repository."""
from datetime import datetime
from uuid import uuid4
from app.database.models import ListingSnapshot
class DynamoDbConfigurationError(Exception): pass
class DynamoDbSnapshotRepository:
    def __init__(self,snapshots_table,runs_table,key_factory=None):
        self._snapshots=snapshots_table; self._runs=runs_table; self._key_factory=key_factory
    @staticmethod
    def partition_key(seller_id,marketplace_id,asin): return f"{seller_id}#{marketplace_id}#{asin}"
    def save_listing_snapshot(self,listing,captured_at=None):
        candidate=ListingSnapshot.from_listing(listing,captured_at=captured_at); latest=self.get_latest_listing(candidate.seller_id,candidate.marketplace_id,candidate.asin); changed=latest is None or latest.listing_hash != candidate.listing_hash; snapshot=ListingSnapshot.from_listing(listing,changed,candidate.captured_at)
        item=self._snapshot_item(snapshot); self._snapshots.put_item(Item=item); return snapshot
    def get_latest_listing(self,seller_id,marketplace_id,asin):
        records=self.get_listing_history(seller_id,marketplace_id,asin,1); return records[0] if records else None
    def get_listing_history(self,seller_id,marketplace_id,asin,limit=30):
        response=self._snapshots.query(KeyConditionExpression=self._key("seller_marketplace_asin").eq(self.partition_key(seller_id,marketplace_id,asin)),ScanIndexForward=False,Limit=max(1,min(limit,100)))
        return [self._to_snapshot(item) for item in response.get("Items",[])]
    def find_changed_listings(self,seller_id,marketplace_id,since_timestamp):
        response=self._snapshots.scan(); prefix=f"{seller_id}#{marketplace_id}#"
        return [self._to_snapshot(item) for item in response.get("Items",[]) if item.get("seller_marketplace_asin","").startswith(prefix) and item.get("changed") and item.get("captured_at","") >= since_timestamp.isoformat()]
    def count_snapshots(self,seller_id,marketplace_id):
        response=self._snapshots.scan(); prefix=f"{seller_id}#{marketplace_id}#"; return sum(1 for item in response.get("Items",[]) if item.get("seller_marketplace_asin","").startswith(prefix))
    def list_tracked_asins(self,seller_id,marketplace_id):
        prefix=f"{seller_id}#{marketplace_id}#"; return sorted({item.get("asin") for item in self._snapshots.scan().get("Items",[]) if item.get("seller_marketplace_asin","").startswith(prefix) and item.get("asin")})
    def save_snapshot_run(self,result):
        run_id=str(uuid4()); self._runs.put_item(Item={"run_id":run_id,"started_at":result.started_at.isoformat(),"finished_at":result.finished_at.isoformat(),"success":result.success,"listings_fetched":result.listings_fetched,"snapshots_saved":result.snapshots_saved,"changed_count":result.changed_count,"unchanged_count":result.unchanged_count,"failed_count":result.failed_count,"pages_processed":result.pages_processed,"error_summary":"; ".join(result.errors) or None}); return run_id
    def _key(self,name):
        if self._key_factory: return self._key_factory(name)
        try:
            from boto3.dynamodb.conditions import Key
        except ImportError as error: raise DynamoDbConfigurationError("DynamoDB support is unavailable") from error
        return Key(name)
    def _snapshot_item(self,s):
        return {"seller_marketplace_asin":self.partition_key(s.seller_id,s.marketplace_id,s.asin),"captured_at":s.captured_at.isoformat(),"seller_id":s.seller_id,"marketplace_id":s.marketplace_id,"sku":s.sku,"asin":s.asin,"title":s.title,"brand":s.brand,"product_type":s.product_type,"condition":s.condition,"listing_status":s.listing_status,"price":s.price,"currency":s.currency,"fulfillment_channel":s.fulfillment_channel,"listing_hash":s.listing_hash,"changed":s.changed}
    @staticmethod
    def _to_snapshot(item):
        return ListingSnapshot(None,item["seller_id"],item["marketplace_id"],datetime.fromisoformat(item["captured_at"]),item["sku"],item["asin"],item.get("title"),item.get("brand"),item.get("product_type"),item.get("condition"),item.get("listing_status"),item.get("price"),item.get("currency"),item.get("fulfillment_channel"),item["listing_hash"],bool(item["changed"]))

