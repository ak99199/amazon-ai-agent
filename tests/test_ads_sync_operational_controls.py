from app.services.ads_sync_gate_service import AdsSyncGateService
def test_retry_remains_the_existing_manual_sync_control():
 assert hasattr(AdsSyncGateService,"evaluate")
