from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from app.amazon_ads.auth import AdsAuthenticationError
import json
from urllib.parse import urlsplit,parse_qs
import boto3
import pytest
from tests.test_dashboard import configure_admin,login

def test_web_lambda_handler_imports_and_assets_exist():
    from web_lambda_handler import handler
    assert handler is not None
    assert Path("templates/dashboard.html").exists()
    assert Path("static/styles.css").exists()
def test_web_lambda_preserves_public_health_and_protected_dashboard():
    client=TestClient(app)
    assert client.get("/health").status_code == 200
    response=client.get("/dashboard",follow_redirects=False)
    assert response.status_code in (303,503)
    assert "secret" not in response.text.lower()

@pytest.fixture
def oauth(monkeypatch):
    from main import AdsLwaAuthenticator
    configure_admin(monkeypatch)
    monkeypatch.setenv("AMAZON_ADS_SECRET_ARN","existing-ads-secret")
    monkeypatch.setenv("AMAZON_ADS_REDIRECT_URI","https://example.com/")
    # The first authorization must work without an existing refresh token.
    secret={"AMAZON_ADS_CLIENT_ID":"client-id","AMAZON_ADS_CLIENT_SECRET":"client-secret","EXTRA":"preserved"}
    seen=[]
    class Store:
        fail=False
        writes=0
        def get_secret_value(self,**kwargs):
            assert kwargs=={"SecretId":"existing-ads-secret"}
            return {"SecretString":json.dumps(secret)}
        def put_secret_value(self,**kwargs):
            if self.fail:raise RuntimeError("private-refresh-token")
            assert kwargs["SecretId"]=="existing-ads-secret"
            secret.update(json.loads(kwargs["SecretString"]))
            self.writes+=1
            seen.append("saved")
    store=Store()
    monkeypatch.setattr(boto3,"client",lambda name:store if name=="secretsmanager" else pytest.fail("Unexpected AWS service"))
    def exchange(self,code,uri):
        assert self._settings.client_id==secret["AMAZON_ADS_CLIENT_ID"]
        seen.append((code,uri))
        return "private-refresh-token"
    monkeypatch.setattr(AdsLwaAuthenticator,"exchange_authorization_code",exchange)
    client=TestClient(app)
    login(client)
    return client,store,secret,seen

def start_oauth(client):
    start=client.get("/api/ads/oauth/start",follow_redirects=False)
    assert start.status_code==303
    destination=urlsplit(start.headers["location"])
    assert destination.scheme=="https" and destination.netloc=="www.amazon.com" and destination.path=="/ap/oa"
    query=parse_qs(destination.query)
    assert query["scope"]==["advertising::campaign_management"]
    return query["state"][0]

def test_root_ads_callback_persists_before_success_and_rejects_replay(oauth):
    client,store,secret,seen=oauth
    state=start_oauth(client)
    params={"code":"private-code","scope":"advertising::campaign_management","state":state}
    response=client.get("/",params=params)
    assert response.status_code==200 and seen==[("private-code","https://example.com/"),"saved"]
    assert secret["AMAZON_ADS_REFRESH_TOKEN"]=="private-refresh-token" and secret["EXTRA"]=="preserved"
    assert "authorization successful" in response.text.lower() and response.headers["cache-control"]=="no-store"
    assert all(secret not in response.text for secret in ("private-code","private-refresh-token","client-secret"))
    assert client.get("/",params=params).status_code==400 and store.writes==1
    assert client.get("/health").status_code==200

def test_root_ads_callback_fails_safely_without_code_state_or_configuration(oauth,monkeypatch):
    client,store,_,seen=oauth
    assert client.get("/").status_code==400
    state=start_oauth(client)
    assert client.get("/",params={"code":"private-code","state":"incorrect"}).status_code==400
    assert client.get("/",params={"code":"private-code","state":"\u2603"}).status_code==400
    assert seen==[] and store.writes==0
    monkeypatch.delenv("AMAZON_ADS_SECRET_ARN",raising=False)
    assert client.get("/",params={"code":"private-code","state":state}).status_code==503
    assert seen==[] and store.writes==0
    assert TestClient(app).get("/api/ads/oauth/start",follow_redirects=False).status_code==401

@pytest.mark.parametrize("failure",["exchange","persistence"])
def test_root_ads_callback_redacts_failures_and_never_claims_success(oauth,monkeypatch,failure):
    from main import AdsLwaAuthenticator
    client,store,secret,_=oauth
    state=start_oauth(client)
    def rejected(self,code,uri):raise AdsAuthenticationError("private-code private-token")
    if failure=="exchange":monkeypatch.setattr(AdsLwaAuthenticator,"exchange_authorization_code",rejected)
    else:store.fail=True
    response=client.get("/",params={"code":"private-code","state":state})
    assert response.status_code==(502 if failure=="exchange" else 503)
    assert store.writes==0 and "AMAZON_ADS_REFRESH_TOKEN" not in secret
    assert all(value not in response.text for value in ("private-code","private-token","private-refresh-token","successful"))
