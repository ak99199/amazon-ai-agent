import pytest
from app.amazon.client import AmazonSPAPIClient,AmazonClientError
from app.amazon.listings import AmazonListingsService
class Auth:
    def get_access_token(self): return "hidden-token"
class Response:
    def __init__(self,status,payload=None): self.status_code=status; self.ok=status<400; self.payload=payload or {}
    def json(self): return self.payload
class Session:
    def __init__(self,responses): self.responses=iter(responses); self.headers=None; self.params=None
    def get(self,*args,**kwargs): self.headers=kwargs["headers"]; self.params=kwargs["params"]; return next(self.responses)
def test_listings_normalize_and_paginate():
    session=Session([Response(200,{"items":[{"sku":"SKU","summaries":[{"asin":"B012345678","status":["ACTIVE"]}],"attributes":{"item_name":["Title"]},"buyer":{"email":"never"}}],"nextToken":"next"})])
    page=AmazonListingsService(AmazonSPAPIClient(Auth(),session)).search_listings("seller","marketplace",10)
    assert page.next_token == "next" and page.listings[0].title == "Title" and "never" not in str(page.listings[0].public_dict())
def test_401_and_403_are_safe():
    for status in (401,403):
        with pytest.raises(AmazonClientError) as error: AmazonSPAPIClient(Auth(),Session([Response(status)])).get("items")
        assert error.value.status_code == status
def test_429_retries(monkeypatch):
    monkeypatch.setattr("app.amazon.client.sleep",lambda delay: None)
    assert AmazonSPAPIClient(Auth(),Session([Response(429),Response(200,{})])).get("items") == {}
