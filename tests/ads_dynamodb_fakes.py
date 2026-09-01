from copy import deepcopy
from types import SimpleNamespace
class ConditionalCheckFailedException(Exception):pass

def decode(value):
 if "S" in value:return value["S"]
 if "N" in value:return int(value["N"]) if "." not in value["N"] else __import__('decimal').Decimal(value["N"])
 if "BOOL" in value:return value["BOOL"]
 return None
def item(value):return {key:decode(part) for key,part in value.items()}
class Client:
 def __init__(self,store):self.store=store;self.fail=False;self.calls=[]
 def transact_write_items(self,TransactItems):
  self.calls.append(TransactItems)
  if self.fail:raise RuntimeError("transaction failed")
  candidate=deepcopy(self.store)
  for action in TransactItems:
   name,payload=next(iter(action.items()));table=candidate[payload["TableName"]]
   source=item(payload.get("Item") or payload.get("Key"));key=(source["scope_key"],source.get("performance_key",source.get("run_key")));current=table.get(key);condition=payload.get("ConditionExpression","")
   values={k:decode(v) for k,v in payload.get("ExpressionAttributeValues",{}).items()}
   if "attribute_not_exists(scope_key)" in condition and current is not None:raise ConditionalCheckFailedException()
   if "#status IN" in condition and (not current or current.get("status") not in ("running","starting")):raise ConditionalCheckFailedException()
   if "#status = :running" in condition and (not current or current.get("status")!="running" or current.get("started_at")>values[":cutoff"]):raise ConditionalCheckFailedException()
   if "sync_id = :sync" in condition and (not current or current.get("sync_id")!=values[":sync"]):raise ConditionalCheckFailedException()
   if "started_at <= :cutoff" in condition and current.get("started_at")>values[":cutoff"]:raise ConditionalCheckFailedException()
   if "attribute_not_exists(started_at) OR" in condition and current and current.get("started_at")>values[":started"]:raise ConditionalCheckFailedException()
   if name=="Put":table[key]=source
   elif name=="Delete":table.pop(key,None)
  for name in self.store:
   self.store[name].clear();self.store[name].update(candidate[name])
class Table:
 def __init__(self,name,store,client):self.name=name;self.store=store[name];self.meta=SimpleNamespace(client=client)
 def get_item(self,Key,**kwargs):return {"Item":deepcopy(self.store.get((Key["scope_key"],Key["run_key"])))} if (Key["scope_key"],Key["run_key"]) in self.store else {}
 def query(self,**kwargs):
  values=kwargs["ExpressionAttributeValues"];scope=values[":scope"];prefix=values[":prefix"];sort="performance_key" if prefix=="PERF#" else "run_key"
  rows=[deepcopy(value) for (pk,sk),value in self.store.items() if pk==scope and sk.startswith(prefix)]
  rows.sort(key=lambda value:value[sort],reverse=not kwargs.get("ScanIndexForward",True));return {"Items":rows[:kwargs.get("Limit",len(rows))]}
class Resource:
 def __init__(self):
  self.store={"performance":{},"runs":{}};self.client=Client(self.store)
  self.tables={name:Table(name,self.store,self.client) for name in self.store}
 def Table(self,name):return self.tables[name]
