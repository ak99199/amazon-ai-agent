"""Safe AWS Secrets Manager loading for Lambda."""
import json
class SecretLoadError(Exception): pass
def load_sp_api_secret(secret_arn,client):
    try: response=client.get_secret_value(SecretId=secret_arn); data=json.loads(response["SecretString"])
    except Exception as error: raise SecretLoadError("Unable to load Amazon credentials") from error
    fields=("SP_API_CLIENT_ID","SP_API_CLIENT_SECRET","SP_API_REFRESH_TOKEN")
    if not all(isinstance(data.get(field),str) and data[field] for field in fields): raise SecretLoadError("Amazon credential secret is incomplete")
    return {field:data[field] for field in fields}

def load_ads_secret(secret_arn,client):
    try:
        response=client.get_secret_value(SecretId=secret_arn);data=json.loads(response["SecretString"])
    except Exception:raise SecretLoadError("Unable to load Amazon Ads credentials") from None
    fields=("AMAZON_ADS_CLIENT_ID","AMAZON_ADS_CLIENT_SECRET","AMAZON_ADS_REFRESH_TOKEN")
    if not isinstance(data,dict) or not all(isinstance(data.get(field),str) and bool(data[field].strip()) for field in fields):raise SecretLoadError("Amazon Ads credential secret is incomplete")
    return {field:data[field].strip() for field in fields}
