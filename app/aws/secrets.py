"""Safe AWS Secrets Manager loading for Lambda."""
import json
class SecretLoadError(Exception): pass
def load_sp_api_secret(secret_arn,client):
    try: response=client.get_secret_value(SecretId=secret_arn); data=json.loads(response["SecretString"])
    except Exception as error: raise SecretLoadError("Unable to load Amazon credentials") from error
    fields=("SP_API_CLIENT_ID","SP_API_CLIENT_SECRET","SP_API_REFRESH_TOKEN")
    if not all(isinstance(data.get(field),str) and data[field] for field in fields): raise SecretLoadError("Amazon credential secret is incomplete")
    return {field:data[field] for field in fields}

def load_ads_secret(secret_arn,client,require_refresh_token=True):
    try:
        response=client.get_secret_value(SecretId=secret_arn);data=json.loads(response["SecretString"])
    except Exception:raise SecretLoadError("Unable to load Amazon Ads credentials") from None
    fields=("AMAZON_ADS_CLIENT_ID","AMAZON_ADS_CLIENT_SECRET")
    if require_refresh_token:fields+=("AMAZON_ADS_REFRESH_TOKEN",)
    if not isinstance(data,dict) or not all(isinstance(data.get(field),str) and bool(data[field].strip()) for field in fields):raise SecretLoadError("Amazon Ads credential secret is incomplete")
    return {field:data[field].strip() for field in fields}

def save_ads_refresh_token(secret_arn,refresh_token,client,expected_client_id):
    """Update the existing Ads secret, preserving credentials and unrelated fields."""
    try:
        if not isinstance(refresh_token,str) or not refresh_token.strip():raise ValueError()
        data=json.loads(client.get_secret_value(SecretId=secret_arn)["SecretString"])
        if not isinstance(data,dict) or data.get("AMAZON_ADS_CLIENT_ID","").strip()!=expected_client_id:
            raise ValueError()
        if not isinstance(data.get("AMAZON_ADS_CLIENT_SECRET"),str) or not data["AMAZON_ADS_CLIENT_SECRET"].strip():
            raise ValueError()
        data["AMAZON_ADS_REFRESH_TOKEN"]=refresh_token
        client.put_secret_value(SecretId=secret_arn,SecretString=json.dumps(data))
    except Exception:
        raise SecretLoadError("Unable to save Amazon Ads credentials") from None
