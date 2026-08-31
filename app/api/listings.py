from fastapi import APIRouter,HTTPException,Query
from app.config import Settings,ConfigurationError
from app.amazon.auth import LwaAuthenticator,AuthenticationError
from app.amazon.client import AmazonSPAPIClient,AmazonClientError
from app.amazon.listings import AmazonListingsService
from app.database.repository import ListingSnapshotRepository
from app.services.listing_service import ListingService
from app.services.listing_history_service import ListingHistoryService
router=APIRouter(prefix="/api",tags=["listings"])
def build_listing_service(settings): return ListingService(AmazonListingsService(AmazonSPAPIClient(LwaAuthenticator(settings))))
@router.get("/listings")
def get_listings(limit:int=Query(10,ge=1,le=20),page_token:str|None=Query(None,max_length=512)):
    settings=Settings.from_environment()
    try:
        settings.require_complete(); page=build_listing_service(settings).get_listings(settings.seller_id or "",settings.marketplace_id or "",limit,page_token)
    except ConfigurationError: raise HTTPException(503,"Amazon listing connection is not configured") from None
    except AuthenticationError: raise HTTPException(502,"Amazon authentication failed") from None
    except AmazonClientError: raise HTTPException(502,"Amazon listing request failed") from None
    return {"listings":[item.public_dict() for item in page.listings],"next_token":page.next_token}
@router.get("/listings/{asin}/history")
def get_listing_history(asin:str,limit:int=Query(30,ge=1,le=100)):
    settings=Settings.from_environment()
    try: settings.require_complete()
    except ConfigurationError: raise HTTPException(503,"Amazon listing connection is not configured") from None
    service=ListingHistoryService(ListingSnapshotRepository())
    history=service.get_history(settings.seller_id or "",settings.marketplace_id or "",asin,limit)
    trend=service.get_trend(settings.seller_id or "",settings.marketplace_id or "",asin,limit)
    return {"history":[snapshot.public_dict() for snapshot in history],"trend":trend.public_dict()}
