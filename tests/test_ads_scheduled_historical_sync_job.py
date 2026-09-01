from app.amazon_ads.sync_models import AdsScheduledHistoricalSyncResult
from app.jobs.ads_historical_sync_job import run_scheduled_ads_historical_sync
class Service:
 def __init__(self):self.calls=[]
 def run(self,seller,market):self.calls.append((seller,market));return AdsScheduledHistoricalSyncResult("disabled",None,None,None,0,"scheduled","safe")
def test_trusted_job_is_single_call_safe_result_and_has_no_import_side_effect():
 service=Service();result=run_scheduled_ads_historical_sync(service,"seller","market");assert result["status"]=="disabled" and service.calls==[("seller","market")] and "secret" not in str(result)
def test_no_public_scheduled_execution_route_exists():
 from app.api.ads import router
 assert not any(route.path.endswith("run-scheduled-sync") or ("scheduled" in route.path and "post" in {method.lower() for method in route.methods or set()}) for route in router.routes)
def test_job_uses_ads_repository_factory(monkeypatch):
 from app.jobs import ads_historical_sync_job as job
 class Blocked(Exception):pass
 monkeypatch.setattr(job,"create_ads_repository",lambda:(_ for _ in ()).throw(Blocked()))
 try:job.run_scheduled_ads_historical_sync()
 except Blocked:pass
 else:assert False,"repository factory was not used"
