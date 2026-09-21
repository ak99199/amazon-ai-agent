from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from secrets import token_urlsafe, compare_digest
from urllib.parse import urlencode
from fastapi.staticfiles import StaticFiles
from os import getenv
from starlette.middleware.sessions import SessionMiddleware
from app.api.listings import router as listings_router
from app.api.internal import router as internal_router
from app.api.alerts import router as alerts_router
from app.api.ads import router as ads_router
from app.web.routes import router as web_router
from app.security.auth import router as auth_router,session_secret,session_secure
from app.security.middleware import DashboardSecurityMiddleware
from app.amazon_ads.auth import AdsAuthenticationError, AdsLwaAuthenticator
from app.amazon_ads.config import AdsSettings
from app.aws.secrets import SecretLoadError, load_ads_secret, save_ads_refresh_token
app=FastAPI(title="Amazon Listing Data Engine")
app.add_middleware(DashboardSecurityMiddleware)
app.add_middleware(SessionMiddleware,secret_key=session_secret(),https_only=session_secure(),same_site="lax",max_age=28800)
app.mount("/static",StaticFiles(directory="static"),name="static")
app.include_router(auth_router); app.include_router(listings_router); app.include_router(internal_router); app.include_router(alerts_router); app.include_router(ads_router); app.include_router(web_router)

def _ads_oauth_configuration():
    secret_arn=getenv("AMAZON_ADS_SECRET_ARN")
    redirect_uri=getenv("AMAZON_ADS_REDIRECT_URI")
    if not secret_arn or not redirect_uri:
        raise HTTPException(503,"Amazon Ads OAuth is not configured")
    try:
        import boto3
        client=boto3.client("secretsmanager")
        secret=load_ads_secret(secret_arn,client,require_refresh_token=False)
    except Exception:
        raise HTTPException(503,"Amazon Ads OAuth is unavailable") from None
    settings=AdsSettings(secret["AMAZON_ADS_CLIENT_ID"],secret["AMAZON_ADS_CLIENT_SECRET"],None,None)
    return secret_arn,redirect_uri,client,settings

@app.get("/api/ads/oauth/start")
def start_amazon_ads_oauth(request:Request):
    # Existing /api/ads middleware requires an authenticated administrator.
    _,redirect_uri,_,settings=_ads_oauth_configuration()
    state=token_urlsafe(32)
    request.session["ads_oauth_state"]=state
    query=urlencode({"client_id":settings.client_id,"scope":"advertising::campaign_management",
                     "response_type":"code","redirect_uri":redirect_uri,"state":state})
    return RedirectResponse("https://www.amazon.com/ap/oa?"+query,303)

@app.get("/",response_class=PlainTextResponse)
def amazon_ads_oauth_callback(request:Request,code:str|None=None,state:str|None=None):
    if not code:raise HTTPException(400,"Authorization code is missing")
    expected=request.session.get("ads_oauth_state")
    if not request.session.get("authenticated") or not state or not expected or not compare_digest(state.encode(),expected.encode()):
        raise HTTPException(400,"Invalid authorization state. Start authorization again.")
    request.session.pop("ads_oauth_state",None)
    secret_arn,redirect_uri,client,settings=_ads_oauth_configuration()
    try:refresh_token=AdsLwaAuthenticator(settings).exchange_authorization_code(code,redirect_uri)
    except AdsAuthenticationError:raise HTTPException(502,"Amazon Ads authorization failed") from None
    try:save_ads_refresh_token(secret_arn,refresh_token,client,settings.client_id)
    except SecretLoadError:raise HTTPException(503,"Amazon Ads authorization could not be saved. Start authorization again.") from None
    return PlainTextResponse("Amazon Ads authorization successful. You may close this page.",headers={"Cache-Control":"no-store"})
@app.get("/health")
def health_check(): return {"status":"ok"}
