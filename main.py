from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.listings import router as listings_router
from app.api.internal import router as internal_router
from app.web.routes import router as web_router
app=FastAPI(title="Amazon Listing Data Engine")
app.mount("/static",StaticFiles(directory="static"),name="static")
app.include_router(listings_router)
app.include_router(internal_router)
app.include_router(web_router)
@app.get("/health")
def health_check(): return {"status":"ok"}
