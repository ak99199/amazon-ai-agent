import os
import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("AMAZON_SP_API_CLIENT_ID")
client_secret = os.getenv("AMAZON_SP_API_CLIENT_SECRET")
refresh_token = os.getenv("AMAZON_SP_REFRESH_TOKEN")

print("Testing Amazon SP-API authentication...")

response = requests.post(
    "https://api.amazon.com/auth/o2/token",
    data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    },
    timeout=30,
)

print("HTTP Status:", response.status_code)

if response.ok:
    data = response.json()
    print("SUCCESS: Amazon authentication is working.")
    print("Access token received:", bool(data.get("access_token")))
else:
    print("FAILED: Amazon authentication did not work.")
    print("Amazon response:", response.text)