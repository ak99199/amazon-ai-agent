import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("AMAZON_SP_API_CLIENT_ID")
client_secret = os.getenv("AMAZON_SP_API_CLIENT_SECRET")
refresh_token = os.getenv("AMAZON_SP_REFRESH_TOKEN")
seller_id = os.getenv("AMAZON_SELLER_ID")
marketplace_id = os.getenv("AMAZON_MARKETPLACE_ID")

print("Testing real Amazon SP-API connection...")
print("Client ID configured:", bool(client_id))
print("Client Secret configured:", bool(client_secret))
print("Refresh Token configured:", bool(refresh_token))
print("Seller ID configured:", bool(seller_id))
print("Marketplace ID:", marketplace_id)

# Amazon India uses the Europe SP-API endpoint.
sp_api_base = "https://sellingpartnerapi-eu.amazon.com"

# Step 1: Get LWA access token
token_response = requests.post(
    "https://api.amazon.com/auth/o2/token",
    data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    },
    timeout=30,
)

print("\nLWA HTTP Status:", token_response.status_code)

if not token_response.ok:
    print("LWA authentication failed.")
    print("Amazon response:", token_response.text)
    raise SystemExit(1)

access_token = token_response.json().get("access_token")

print("LWA authentication: SUCCESS")
print("Access token received:", bool(access_token))

# Step 2: Make a read-only Listings Items request
url = f"{sp_api_base}/listings/2021-08-01/items/{seller_id}"

params = {
    "marketplaceIds": marketplace_id,
    "includedData": "summaries",
    "pageSize": 1,
}

headers = {
    "x-amz-access-token": access_token,
    "accept": "application/json",
}

response = requests.get(
    url,
    params=params,
    headers=headers,
    timeout=30,
)

print("\nSP-API HTTP Status:", response.status_code)

try:
    data = response.json()
except ValueError:
    print("Non-JSON response:")
    print(response.text)
    raise SystemExit(1)

if response.ok:
    print("SUCCESS: Real SP-API request worked.")
    print("Response keys:", list(data.keys()))
else:
    print("SP-API request failed.")
    print(json.dumps(data, indent=2))