import os,sys,types
from datetime import datetime,timezone
import lambda_handler
from app.services.snapshot_collector import CollectionResult
def result(): return CollectionResult(datetime.now(timezone.utc),datetime.now(timezone.utc),1,1,1,0,0,1,True,())
def test_lambda_missing_config_is_sanitized(monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND",raising=False)
    response=lambda_handler.lambda_handler({},None)
    assert not response["success"] and "SECRET_ARN" not in str(response)
def test_lambda_success_and_event_limits(monkeypatch):
    class SecretClient:
        def get_secret_value(self,**kwargs): return {"SecretString":"{\"SP_API_CLIENT_ID\":\"id\",\"SP_API_CLIENT_SECRET\":\"secret\",\"SP_API_REFRESH_TOKEN\":\"refresh\"}"}
    class Resource:
        def Table(self,name): return object()
    fake=types.SimpleNamespace(client=lambda name:SecretClient(),resource=lambda name:Resource())
    monkeypatch.setitem(sys.modules,"boto3",fake)
    for key,value in {"STORAGE_BACKEND":"dynamodb","SECRET_ARN":"arn","SELLER_ID":"seller","MARKETPLACE_ID":"market","DYNAMODB_SNAPSHOTS_TABLE":"snapshots","DYNAMODB_RUNS_TABLE":"runs"}.items(): monkeypatch.setenv(key,value)
    monkeypatch.setattr(lambda_handler,"run_listing_snapshot_job",lambda *args: result())
    response=lambda_handler.lambda_handler({"max_pages":9999,"page_size":0},None)
    assert response["success"] and response["snapshots_saved"] == 1 and "secret" not in str(response)
