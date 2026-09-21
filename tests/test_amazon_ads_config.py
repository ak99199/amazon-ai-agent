import pytest
from app.amazon_ads.config import AdsConfigurationError,AdsSettings

def test_ads_variables_are_separate_and_region_defaults(monkeypatch):
    for key in ("AMAZON_ADS_SECRET_ARN","AMAZON_ADS_CLIENT_ID","AMAZON_ADS_CLIENT_SECRET","AMAZON_ADS_REFRESH_TOKEN","AMAZON_ADS_PROFILE_ID","AMAZON_ADS_REGION"):monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv("AMAZON_SP_API_CLIENT_ID","sp-api-id");settings=AdsSettings.from_environment()
    assert settings.client_id is None and settings.region=="FE" and settings.base_url=="https://advertising-api-fe.amazon.com"
def test_ads_config_validation_is_safe(monkeypatch):
    settings=AdsSettings(None,"secret","refresh",None,"FE")
    with pytest.raises(AdsConfigurationError) as error:settings.require_auth()
    assert "secret" not in str(error.value).lower() and "refresh" not in str(error.value).lower()
    with pytest.raises(AdsConfigurationError):AdsSettings("id","secret","refresh",None,"FE").require_profile_api()

def test_ads_settings_load_existing_secret_and_preserve_local_fallback(monkeypatch):
    import boto3,json
    from app.services.ads_production_readiness_service import AdsProductionReadinessService
    credentials={"AMAZON_ADS_CLIENT_ID":"stored-id","AMAZON_ADS_CLIENT_SECRET":"stored-secret","AMAZON_ADS_REFRESH_TOKEN":"stored-refresh"}
    for name in credentials:monkeypatch.setenv(name,"local-value")
    monkeypatch.setenv("AMAZON_ADS_SECRET_ARN","configured-secret")
    monkeypatch.setenv("AMAZON_ADS_REGION","FE")
    monkeypatch.delenv("AMAZON_ADS_PROFILE_ID",raising=False)
    class Client:
        def get_secret_value(self,**kwargs):
            assert kwargs=={"SecretId":"configured-secret"}
            return {"SecretString":json.dumps(credentials)}
    calls=[]
    monkeypatch.setattr(boto3,"client",lambda name:calls.append(name) or Client())
    settings=AdsSettings.from_environment()
    assert (settings.client_id,settings.client_secret,settings.refresh_token)==tuple(credentials.values())
    assert settings.profile_id is None and settings.region=="FE" and calls==["secretsmanager"]
    public=AdsProductionReadinessService(settings=settings).get().public_dict()
    assert public["credential_configuration_complete"] and not public["profile_selected"]
    assert all(value not in str(public) for value in credentials.values())
    monkeypatch.delenv("AMAZON_ADS_SECRET_ARN")
    assert AdsSettings.from_environment().refresh_token=="local-value" and calls==["secretsmanager"]

@pytest.mark.parametrize("failure",["client","read","incomplete"])
def test_secret_configuration_fails_closed_without_sensitive_exception(monkeypatch,failure):
    import boto3,traceback
    monkeypatch.setenv("AMAZON_ADS_SECRET_ARN","configured-secret")
    for name in ("AMAZON_ADS_CLIENT_ID","AMAZON_ADS_CLIENT_SECRET","AMAZON_ADS_REFRESH_TOKEN"):
        monkeypatch.setenv(name,"local-fallback-must-not-be-used")
    class Client:
        def get_secret_value(self,**kwargs):
            if failure=="read":raise RuntimeError("sensitive-sentinel")
            return {"SecretString":'{"AMAZON_ADS_CLIENT_SECRET":"sensitive-sentinel"}'}
    def client(name):
        if failure=="client":raise RuntimeError("sensitive-sentinel")
        return Client()
    monkeypatch.setattr(boto3,"client",client)
    with pytest.raises(AdsConfigurationError) as error:AdsSettings.from_environment()
    assert "sensitive-sentinel" not in "".join(traceback.format_exception(error.value))
    assert str(error.value)=="Amazon Ads credentials are unavailable"
