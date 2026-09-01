import json,pytest
from app.aws.secrets import SecretLoadError,load_ads_secret,load_sp_api_secret
class Client:
    def __init__(self,value): self.value=value
    def get_secret_value(self,**kwargs): return {"SecretString":self.value}
def test_secret_parsing():
    data=load_sp_api_secret("arn",Client(json.dumps({"SP_API_CLIENT_ID":"id","SP_API_CLIENT_SECRET":"secret","SP_API_REFRESH_TOKEN":"refresh"})))
    assert data["SP_API_CLIENT_ID"] == "id" and "secret" not in str({"configured":bool(data)})
def test_missing_secret_is_safe():
    with pytest.raises(SecretLoadError): load_sp_api_secret("arn",Client("{}"))

def test_ads_secret_parsing_returns_only_required_fields():
 value={"AMAZON_ADS_CLIENT_ID":"ads-id","AMAZON_ADS_CLIENT_SECRET":"ads-secret","AMAZON_ADS_REFRESH_TOKEN":"ads-refresh","EXTRA":"ignored"}
 assert load_ads_secret("arn",Client(json.dumps(value)))=={key:value[key] for key in value if key!="EXTRA"}

@pytest.mark.parametrize("value",[
 {"AMAZON_ADS_CLIENT_ID":"id","AMAZON_ADS_CLIENT_SECRET":"secret"},
 {"AMAZON_ADS_CLIENT_ID":"id","AMAZON_ADS_CLIENT_SECRET":" ","AMAZON_ADS_REFRESH_TOKEN":"refresh"},
 "not-json",
])
def test_invalid_ads_secrets_are_sanitized(value):
 raw=value if isinstance(value,str) else json.dumps(value)
 with pytest.raises(SecretLoadError) as error:load_ads_secret("private-arn",Client(raw))
 assert "private-arn" not in str(error.value) and "ads-secret" not in str(error.value)

def test_ads_secrets_manager_failure_is_sanitized():
 class Broken:
  def get_secret_value(self,**kwargs):raise RuntimeError("request-id private-secret-value")
 with pytest.raises(SecretLoadError) as error:load_ads_secret("private-arn",Broken())
 assert "request-id" not in str(error.value) and "private" not in str(error.value)
