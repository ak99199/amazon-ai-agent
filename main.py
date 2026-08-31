from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.api.listings import router as listings_router
from app.api.internal import router as internal_router
from app.web.routes import router as web_router
from app.security.auth import router as auth_router,session_secret,session_secure
from app.security.middleware import DashboardSecurityMiddleware
app=FastAPI(title="Amazon Listing Data Engine")
app.add_middleware(DashboardSecurityMiddleware)
app.add_middleware(SessionMiddleware,secret_key=session_secret(),https_only=session_secure(),same_site="lax",max_age=28800)
app.mount("/static",StaticFiles(directory="static"),name="static")
app.include_router(auth_router); app.include_router(listings_router); app.include_router(internal_router); app.include_router(web_router)
@app.get("/health")
def health_check(): return {"status":"ok"}
