from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.services.ads_live_read_service import AdsLiveReadService


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

