from fastapi import FastAPI
from app.api.listings import router as listings_router
from app.api.internal import router as internal_router
app=FastAPI(title="Amazon Listing Data Engine")
app.include_router(listings_router)
app.include_router(internal_router)
@app.get("/health")
def health_check(): return {"status":"ok"}
