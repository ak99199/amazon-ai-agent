from fastapi.testclient import TestClient
from app.amazon.listings import ListingPage
from app.amazon.models import Listing
from app.services.listing_service import ListingService
from main import app
class AmazonListings:
    def search_listings(self,*args): return ListingPage([Listing("seller","marketplace","SKU")],"next")
def test_service_layer(): assert ListingService(AmazonListings()).get_listings("seller","marketplace").next_token == "next"
def test_health():
    response=TestClient(app).get("/health")
    assert response.status_code == 200 and response.json() == {"status":"ok"}
def test_listings_missing_configuration(monkeypatch):
    monkeypatch.delenv("AMAZON_SP_API_CLIENT_ID",raising=False)
    response=TestClient(app).get("/api/listings")
    assert response.status_code == 503
