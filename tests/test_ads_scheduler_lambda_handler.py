import importlib,json,sys
from app.api.ads import router

def load(monkeypatch,enabled="false",backend="sqlite"):
 monkeypatch.setenv("AMAZON_ADS_SCHEDULED_SYNC_ENABLED",enabled);monkeypatch.setenv("AMAZON_ADS_STORAGE_BACKEND",backend);monkeypatch.delenv("AMAZON_ADS_DYNAMODB_PERFORMANCE_TABLE",raising=False);monkeypatch.delenv("AMAZON_ADS_DYNAMODB_SYNC_RUNS_TABLE",raising=False);monkeypatch.delenv("AMAZON_ADS_SECRET_ARN",raising=False)
 sys.modules.pop("ads_scheduler_lambda_handler",None);return importlib.import_module("ads_scheduler_lambda_handler")

def test_import_and_disabled_handler_do_not_construct_repository_or_job(monkeypatch):
 from app.jobs import ads_historical_sync_job as job
 calls=[];monkeypatch.setattr(job,"run_scheduled_ads_historical_sync",lambda:calls.append("import-job"));module=load(monkeypatch);assert calls==[]
 monkeypatch.setattr(module,"create_ads_repository",lambda **kwargs:calls.append("repository"));monkeypatch.setattr(module,"_secrets_client",lambda:calls.append("secret-client"));monkeypatch.setattr(module,"run_scheduled_ads_historical_sync",lambda:calls.append("job"))
 assert module.handler({"force":True,"credentials":"secret"},None)["status"]=="disabled" and calls==[]

def test_enabled_sqlite_and_unimplemented_dynamodb_fail_before_job(monkeypatch):
 for backend in ("sqlite","dynamodb"):
  module=load(monkeypatch,"true",backend);calls=[];monkeypatch.setattr(module,"run_scheduled_ads_historical_sync",lambda:calls.append(True))
  result=module.handler({},None);assert result["status"]=="storage_blocked" and calls==[] and "secret" not in str(result).lower()

def test_event_cannot_override_authoritative_configuration(monkeypatch):
 module=load(monkeypatch,"true","sqlite");repository=object();monkeypatch.setattr(module,"create_ads_repository",lambda **kwargs:repository);calls=[];monkeypatch.setenv("AMAZON_ADS_SECRET_ARN","server-arn");monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","server-profile");monkeypatch.setenv("AMAZON_ADS_REGION","EU")
 class Secrets:
  def get_secret_value(self,**kwargs):calls.append(kwargs);return {"SecretString":json.dumps({"AMAZON_ADS_CLIENT_ID":"server-id","AMAZON_ADS_CLIENT_SECRET":"server-client-value","AMAZON_ADS_REFRESH_TOKEN":"server-refresh-value"})}
 monkeypatch.setattr(module,"_secrets_client",lambda:Secrets())
 monkeypatch.setattr(module,"run_scheduled_ads_historical_sync",lambda **kwargs:calls.append(kwargs) or {"status":"not_due","run_id":None,"rows_persisted":0,"message":"safe","seller_id":"server"})
 event={"seller_id":"attacker","marketplace_id":"attacker","profile_id":"attacker","region":"attacker","start_date":"1900-01-01","force":True,"credentials":"secret"}
 result=module.handler(event,None);assert calls[0]=={"SecretId":"server-arn"} and calls[1]["repository"] is repository and calls[1]["settings"].profile_id=="server-profile" and calls[1]["settings"].region=="EU"
 assert result=={"status":"not_due","run_id":None,"rows_persisted":0,"message":"safe"} and "attacker" not in str(result)

def test_missing_secret_reference_blocks_after_persistent_storage(monkeypatch):
 module=load(monkeypatch,"true","dynamodb");repository=object();calls=[];monkeypatch.setattr(module,"create_ads_repository",lambda **kwargs:repository);monkeypatch.setattr(module,"_secrets_client",lambda:calls.append("secret"));monkeypatch.setattr(module,"run_scheduled_ads_historical_sync",lambda **kwargs:calls.append(kwargs))
 assert module.handler({},None)["status"]=="readiness_blocked" and calls==[]

def test_secret_failure_is_sanitized_without_job(monkeypatch):
 module=load(monkeypatch,"true","dynamodb");monkeypatch.setenv("AMAZON_ADS_SECRET_ARN","private-arn");monkeypatch.setattr(module,"create_ads_repository",lambda **kwargs:object())
 class Broken:
  def get_secret_value(self,**kwargs):raise RuntimeError("request-id private-secret-value")
 monkeypatch.setattr(module,"_secrets_client",lambda:Broken());calls=[];monkeypatch.setattr(module,"run_scheduled_ads_historical_sync",lambda **kwargs:calls.append(kwargs))
 result=module.handler({},None);assert result["status"]=="unavailable" and calls==[] and "private" not in str(result) and "request-id" not in str(result)

def test_unexpected_error_is_sanitized(monkeypatch):
 module=load(monkeypatch,"true","sqlite");monkeypatch.setattr(module,"create_ads_repository",lambda **kwargs:(_ for _ in ()).throw(RuntimeError("secret signed URL database path")))
 result=module.handler({},None);assert result["status"]=="unavailable" and "secret" not in str(result).lower() and "signed" not in str(result).lower()

def test_no_public_scheduled_execution_route_exists():
 assert not any("scheduled" in route.path and "post" in {method.lower() for method in route.methods or set()} for route in router.routes)
