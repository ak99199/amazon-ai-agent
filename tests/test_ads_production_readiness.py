import pytest
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.services.ads_production_readiness_service import AdsProductionReadinessService

def result(approval="approved",client_id="configured",secret="configured",refresh="configured",profile="configured",region="FE",live=True,mock=False):return AdsProductionReadinessService(AdsSettings(client_id,secret,refresh,profile,region),AdsLiveReadConfig(live,mock),approval).get()

@pytest.mark.parametrize("kwargs,reason",[({"approval":"pending"},"approval_not_granted"),({"client_id":None},"credential_configuration_incomplete"),({"secret":None},"credential_configuration_incomplete"),({"refresh":None},"credential_configuration_incomplete"),({"profile":None},"profile_not_selected"),({"live":False},"live_read_disabled"),({"mock":True},"mock_mode_enabled"),({"region":"XX"},"region_invalid")])
def test_each_production_gate_blocks(kwargs,reason):
 state=result(**kwargs);assert not state.live_read_ready and not state.manual_smoke_test_allowed and reason in state.blocking_reasons

def test_all_conditions_ready_and_safe_output():
 state=result();public=state.public_dict();assert state.live_read_ready and state.manual_smoke_test_allowed and state.region=="FE" and state.approval_granted
 text=str(public);assert "configured" not in text and "Authorization" not in text

def test_invalid_approval_is_unknown_and_pending_warning_is_safe():
 assert result(approval="invalid").approval_status=="unknown"
 assert "approval is still pending" in result(approval="pending").warnings[0]
