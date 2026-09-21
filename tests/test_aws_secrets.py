import json,pytest
from app.aws.secrets import SecretLoadError,load_ads_secret,load_sp_api_secret,save_ads_refresh_token
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

@pytest.mark.parametrize("previous",[None,"old-refresh"])
def test_ads_refresh_token_persistence_preserves_existing_secret(previous):
 original={"AMAZON_ADS_CLIENT_ID":"id","AMAZON_ADS_CLIENT_SECRET":"secret","EXTRA":{"preserved":True}}
 if previous is not None:original["AMAZON_ADS_REFRESH_TOKEN"]=previous
 class Store(Client):
  def put_secret_value(self,**kwargs):self.written=kwargs
 client=Store(json.dumps(original))
 assert load_ads_secret("existing",client,require_refresh_token=False)=={key:original[key] for key in ("AMAZON_ADS_CLIENT_ID","AMAZON_ADS_CLIENT_SECRET")}
 save_ads_refresh_token("existing","new-refresh",client,"id")
 assert client.written["SecretId"]=="existing"
 assert json.loads(client.written["SecretString"])=={**original,"AMAZON_ADS_REFRESH_TOKEN":"new-refresh"}
 client.value=client.written["SecretString"]
 assert load_ads_secret("existing",client)["AMAZON_ADS_REFRESH_TOKEN"]=="new-refresh"

@pytest.mark.parametrize("failure",["read","write","invalid_json","client_mismatch"])
def test_ads_refresh_persistence_failure_is_safe(failure):
 class Store:
  writes=0
  def get_secret_value(self,**kwargs):
   if failure=="read":raise RuntimeError("private-token")
   return {"SecretString":"not-json" if failure=="invalid_json" else json.dumps({"AMAZON_ADS_CLIENT_ID":"other" if failure=="client_mismatch" else "id","AMAZON_ADS_CLIENT_SECRET":"secret"})}
  def put_secret_value(self,**kwargs):
   self.writes+=1
   raise RuntimeError("private-token")
 client=Store()
 with pytest.raises(SecretLoadError) as error:save_ads_refresh_token("existing","private-token",client,"id")
 assert str(error.value)=="Unable to save Amazon Ads credentials"
 assert client.writes==(1 if failure=="write" else 0)
