from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.services.ads_live_read_service import AdsLiveReadService
from app.services.ads_live_read_service import AdsLiveReadBlockedError
import pytest


def test_live_read_defaults_to_safe_mock_disabled(monkeypatch):
    monkeypatch.delenv("AMAZON_ADS_LIVE_READ_ENABLED",raising=False);monkeypatch.delenv("AMAZON_ADS_USE_MOCK_DATA",raising=False)
    config=AdsLiveReadConfig.from_environment(); assert config.live_read_enabled is False and config.use_mock_data is True
    status=AdsLiveReadService(AdsSettings(None,None,None,None)).status()
    assert status.mode=="mock" and status.ready is False

def test_live_read_blocks_approval_config_and_profile(monkeypatch):
    monkeypatch.setenv("AMAZON_ADS_LIVE_READ_ENABLED","true"); monkeypatch.setenv("AMAZON_ADS_USE_MOCK_DATA","false")
    assert AdsLiveReadService(AdsSettings("id","secret","refresh","profile"),approval_status="pending").status().mode=="blocked_approval"
    assert AdsLiveReadService(AdsSettings(None,None,None,"profile"),approval_status="approved").status().mode=="blocked_config"
    assert AdsLiveReadService(AdsSettings("id","secret","refresh",None),approval_status="approved").status().mode=="blocked_profile"

@pytest.mark.parametrize("approval,secret,region,live,mock",[
    ("pending","secret","FE",True,False),
    ("approved",None,"FE",True,False),
    ("approved","secret","XX",True,False),
    ("approved","secret","FE",False,False),
    ("approved","secret","FE",True,True),
])
def test_profile_discovery_enforces_all_other_gates(approval,secret,region,live,mock):
    class Profiles:
        def list_profiles(self):pytest.fail("Profile dependency must not be called")
    service=AdsLiveReadService(AdsSettings("id",secret,"refresh",None,region),Profiles(),config=AdsLiveReadConfig(live,mock),approval_status=approval)
    assert not service.status(require_profile=False).ready
    with pytest.raises(AdsLiveReadBlockedError):service.discover_profiles()

def test_profile_scoped_reads_still_require_profile():
    service=AdsLiveReadService(AdsSettings("id","secret","refresh",None,"FE"),config=AdsLiveReadConfig(True,False),approval_status="approved")
    assert service.status(require_profile=False).ready and not service.status().ready
    with pytest.raises(AdsLiveReadBlockedError):service.read_entities()

