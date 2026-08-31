import pytest
from app.amazon_ads.config import AdsConfigurationError,AdsSettings

def test_ads_variables_are_separate_and_region_defaults(monkeypatch):
    for key in ("AMAZON_ADS_CLIENT_ID","AMAZON_ADS_CLIENT_SECRET","AMAZON_ADS_REFRESH_TOKEN","AMAZON_ADS_PROFILE_ID","AMAZON_ADS_REGION"):monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv("AMAZON_SP_API_CLIENT_ID","sp-api-id");settings=AdsSettings.from_environment()
    assert settings.client_id is None and settings.region=="FE" and settings.base_url=="https://advertising-api-fe.amazon.com"
def test_ads_config_validation_is_safe(monkeypatch):
    settings=AdsSettings(None,"secret","refresh",None,"FE")
    with pytest.raises(AdsConfigurationError) as error:settings.require_auth()
    assert "secret" not in str(error.value).lower() and "refresh" not in str(error.value).lower()
    with pytest.raises(AdsConfigurationError):AdsSettings("id","secret","refresh",None,"FE").require_profile_api()