import re
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import ads
from main import app
from tests.test_dashboard import configure_admin, login


class Service:
    calls = []

    def __init__(self, *args): pass

    def prepare(self, *args):
        self.calls.append(args)
        return SimpleNamespace(public_dict=lambda: {"status":"prepared",
            "current_value":"1.00","proposed_value":"1.10"})

    def list_intents(self, *args):
        self.calls.append(args)
        return []


def token(client):
    return re.search(r'data-csrf="([^"]+)"', client.get("/dashboard").text).group(1)


def test_write_intent_requires_auth_and_csrf(monkeypatch):
    configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p")
    client=TestClient(app);path="/api/ads/execution-plans/plan/write-intent"
    assert client.post(path,json={"confirm_prepare_write_intent":True}).status_code==401
    login(client)
    assert client.post(path,json={"confirm_prepare_write_intent":True}).status_code==403


def test_write_intent_uses_server_scope_and_ignores_numeric_overrides(monkeypatch):
    configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p")
    monkeypatch.setenv("AMAZON_SELLER_ID","s");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","m")
    Service.calls=[];monkeypatch.setattr(ads,"AdsWriteIntentService",Service)
    client=TestClient(app);login(client)
    response=client.post("/api/ads/execution-plans/plan/write-intent",
        json={"confirm_prepare_write_intent":True,"seller_id":"attacker",
              "current_value":"999","proposed_value":"888","direction":"decrease",
              "endpoint":"https://attacker"},headers={"X-CSRF-Token":token(client)})
    assert response.status_code==200 and response.json()["status"]=="prepared"
    assert Service.calls[0][:5]==("s","m","p","plan",True) and "attacker" not in response.text


def test_write_intent_list_is_authenticated_read_only(monkeypatch):
    configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","p")
    monkeypatch.setenv("AMAZON_SELLER_ID","s");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","m")
    Service.calls=[];monkeypatch.setattr(ads,"AdsWriteIntentService",Service)
    client=TestClient(app)
    assert client.get("/api/ads/write-intents").status_code==401
    login(client);response=client.get("/api/ads/write-intents?status=prepared&limit=10")
    assert response.status_code==200 and response.json()["count"]==0
    assert Service.calls==[("s","m","p","prepared",10)]
