"""Safe AWS Secrets Manager loading for Lambda."""
import json
class SecretLoadError(Exception): pass
def load_sp_api_secret(secret_arn,client):
    try: response=client.get_secret_value(SecretId=secret_arn); data=json.loads(response["SecretString"])
    except Exception as error: raise SecretLoadError("Unable to load Amazon credentials") from error
    fields=("SP_API_CLIENT_ID","SP_API_CLIENT_SECRET","SP_API_REFRESH_TOKEN")
    if not all(isinstance(data.get(field),str) and data[field] for field in fields): raise SecretLoadError("Amazon credential secret is incomplete")
    return {field:data[field] for field in fields}
