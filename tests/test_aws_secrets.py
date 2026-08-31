import json,pytest
from app.aws.secrets import SecretLoadError,load_sp_api_secret
class Client:
    def __init__(self,value): self.value=value
    def get_secret_value(self,**kwargs): return {"SecretString":self.value}
def test_secret_parsing():
    data=load_sp_api_secret("arn",Client(json.dumps({"SP_API_CLIENT_ID":"id","SP_API_CLIENT_SECRET":"secret","SP_API_REFRESH_TOKEN":"refresh"})))
    assert data["SP_API_CLIENT_ID"] == "id" and "secret" not in str({"configured":bool(data)})
def test_missing_secret_is_safe():
    with pytest.raises(SecretLoadError): load_sp_api_secret("arn",Client("{}"))
