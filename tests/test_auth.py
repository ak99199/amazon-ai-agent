import requests
import pytest
from app.amazon.auth import LwaAuthenticator,AuthenticationError
from app.config import Settings
class Response:
    def __init__(self,status,payload=None): self.status_code=status; self.ok=status<400; self.payload=payload or {}
    def json(self): return self.payload
class Session:
    def __init__(self,response): self.response=response
    def post(self,*args,**kwargs): return self.response
def settings(): return Settings("id","secret","refresh","seller","marketplace")
def test_token_retrieval_is_internal(): assert LwaAuthenticator(settings(),Session(Response(200,{"access_token":"token"}))).get_access_token() == "token"
def test_token_failure_redacts_secret():
    with pytest.raises(AuthenticationError) as error: LwaAuthenticator(settings(),Session(Response(401))).get_access_token()
    assert "secret" not in str(error.value).lower() and "refresh" not in str(error.value).lower()
