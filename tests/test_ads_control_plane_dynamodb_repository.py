from datetime import datetime,timezone
from decimal import Decimal
import pytest
from app.database.ads_control_plane_dynamodb_repository import DynamoDbAdsControlPlaneRepository,AdsControlPlaneRepositoryError
from tests.test_ads_write_intent_revalidation import setup
from tests.test_ads_sealed_write_command import setup as command_setup

class Client:
 def __init__(self,fail=False):self.calls=[];self.fail=fail
 def transact_write_items(self,TransactItems):
  self.calls.append(TransactItems)
  if self.fail:raise RuntimeError("fake")
class Table:
 name="control"
 def __init__(self):self.items={}
 def get_item(self,Key,ConsistentRead):return {"Item":self.items.get((Key["PK"],Key["SK"]))}

def intent():
 maker,_,_,_,_,proposal,preflight=__import__("tests.test_ads_write_intent_service",fromlist=["trusted"]).trusted()
 return maker.prepare("s","m","p","plan",True,proposal,preflight)
def test_scoped_keys_serialization_and_atomic_intent_event():
 client=Client();repo=DynamoDbAdsControlPlaneRepository(Table(),client,"control");item=intent();repo.save_write_intent(item)
 tx=client.calls[0];record=tx[0]["Put"]["Item"];event=tx[1]["Put"]["Item"]
 assert record["PK"]=="SELLER#s#MARKETPLACE#m#PROFILE#p" and record["SK"].startswith("WRITE_INTENT#")
 assert isinstance(record["created_at"],str) and event["event_type"]=="WRITE_INTENT_PREPARED"
 assert "access_token" not in str(record).lower() and len(tx)==2
def test_sealed_command_and_event_are_one_transaction():
 service,_,item,target=command_setup();command=service.seal("s","m","p",item.write_intent_id,True,target)
 client=Client();repo=DynamoDbAdsControlPlaneRepository(Table(),client,"control");repo.save_sealed_write_command(command)
 assert len(client.calls)==1 and len(client.calls[0])==2 and client.calls[0][1]["Put"]["Item"]["event_type"]=="WRITE_COMMAND_SEALED"
def test_transaction_failure_is_safe_and_scope_key_isolated():
 repo=DynamoDbAdsControlPlaneRepository(Table(),Client(True),"control")
 with pytest.raises(AdsControlPlaneRepositoryError):repo.save_write_intent(intent())
 assert repo.scope_key("s","m","p")!=repo.scope_key("other","m","p")!=repo.scope_key("other","other","p")
