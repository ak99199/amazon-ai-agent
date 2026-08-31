from fastapi.testclient import TestClient
from main import app
from tests.test_dashboard import configure_admin,login
SENTINELS={"AMAZON_ADS_CLIENT_ID":"TEST_CLIENT_ID_123","AMAZON_ADS_CLIENT_SECRET":"TEST_CLIENT_SECRET_456","AMAZON_ADS_REFRESH_TOKEN":"TEST_REFRESH_TOKEN_789","AMAZON_ADS_PROFILE_ID":"TEST_PROFILE_ID_001"}
def test_ads_api_is_protected_and_redacts_values(monkeypatch):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market")
 for key,value in SENTINELS.items():monkeypatch.setenv(key,value)
 monkeypatch.setenv("AMAZON_ADS_APPROVAL_STATUS","approved")
 client=TestClient(app);assert client.get("/api/ads/readiness").status_code==401;login(client);response=client.get("/api/ads/readiness");payload=response.json()
 assert response.status_code==200
 for key in ("has_client_id","has_client_secret","has_refresh_token","has_profile_id"):assert payload[key] is True
 for value in SENTINELS.values():assert value not in response.text
 for key in ("client_id","client_secret","refresh_token","access_token","authorization"):assert key not in payload
 assert client.get("/api/ads/diagnostics").status_code==200 and client.get("/api/ads/ingestion-runs").status_code==200