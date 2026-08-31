from fastapi import FastAPI
from app.api.listings import router as listings_router
app=FastAPI(title="Amazon Listing Data Engine")
app.include_router(listings_router)
@app.get("/health")
def health_check(): return {"status":"ok"}
