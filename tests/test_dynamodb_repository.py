from datetime import datetime,timezone
from app.amazon.models import Listing
from app.database.dynamodb_repository import DynamoDbSnapshotRepository
class Key:
    def __init__(self,name): self.name=name
    def eq(self,value): self.value=value; return self
class Table:
    def __init__(self): self.items=[]
    def put_item(self,Item): self.items.append(Item)
    def query(self,**kwargs):
        key=kwargs["KeyConditionExpression"].value; items=[item for item in self.items if item.get("seller_marketplace_asin")==key]; return {"Items":sorted(items,key=lambda item:item["captured_at"],reverse=True)[:kwargs["Limit"]]}
    def scan(self): return {"Items":self.items}
def item(seller="s",market="m",price="10"): return Listing(seller,market,"SKU","B012345678",price=price)
def test_dynamodb_insert_latest_history_and_isolation():
    snapshots,runs=Table(),Table(); repo=DynamoDbSnapshotRepository(snapshots,runs,Key); first=repo.save_listing_snapshot(item()); second=repo.save_listing_snapshot(item()); changed=repo.save_listing_snapshot(item(price="11")); repo.save_listing_snapshot(item(seller="other"))
    assert first.changed and not second.changed and changed.changed
    assert len(repo.get_listing_history("s","m","B012345678")) == 3 and repo.count_snapshots("s","m") == 3 and repo.count_snapshots("other","m") == 1
def test_changed_query_is_scoped():
    repo=DynamoDbSnapshotRepository(Table(),Table(),Key); now=datetime.now(timezone.utc); repo.save_listing_snapshot(item(),now); repo.save_listing_snapshot(item(seller="other"),now)
    assert len(repo.find_changed_listings("s","m",now)) == 1
