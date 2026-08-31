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

@router.get("/listings/{asin}/intelligence")
def get_listing_intelligence(asin:str,window:str=Query("30",pattern="^(7|30|60|90|all)$")):
    from app.services.listing_intelligence_service import ListingIntelligenceService
    settings=Settings.from_environment()
    try: settings.require_complete()
    except ConfigurationError: raise HTTPException(503,"Amazon listing connection is not configured") from None
    intelligence=ListingIntelligenceService(ListingSnapshotRepository()).analyze(settings.seller_id or "",settings.marketplace_id or "",asin,window)
    return intelligence.public_dict()

@router.get("/listings/{asin}/recommendations")
def get_listing_recommendations(asin:str,window:str=Query("30",pattern="^(7|30|60|90|all)$")):
    from app.services.listing_intelligence_service import ListingIntelligenceService
    from app.services.listing_recommendation_service import ListingRecommendationService
    settings=Settings.from_environment()
    try: settings.require_complete()
    except ConfigurationError: raise HTTPException(503,"Amazon listing connection is not configured") from None
    intelligence=ListingIntelligenceService(ListingSnapshotRepository()).analyze(settings.seller_id or "",settings.marketplace_id or "",asin,window)
    return ListingRecommendationService().recommend(intelligence).public_dict()

@router.get("/listings/{asin}/explanation")
def get_listing_explanation(asin:str,window:str=Query("30",pattern="^(7|30|60|90|all)$")):
    from app.services.listing_intelligence_service import ListingIntelligenceService
    from app.services.listing_recommendation_service import ListingRecommendationService
    from app.services.recommendation_explanation_service import RecommendationExplanationService
    settings=Settings.from_environment()
    try: settings.require_complete()
    except ConfigurationError: raise HTTPException(503,"Amazon listing connection is not configured") from None
    intelligence=ListingIntelligenceService(ListingSnapshotRepository()).analyze(settings.seller_id or "",settings.marketplace_id or "",asin,window)
    recommendation=ListingRecommendationService().recommend(intelligence)
    return RecommendationExplanationService.from_environment().explain(recommendation).public_dict()

@router.get("/listings/{asin}/insights")
def get_listing_insights(asin:str,window:str=Query("30",pattern="^(7|30|60|90|all)$")):
    from app.services.listing_intelligence_service import ListingIntelligenceService
    from app.services.listing_recommendation_service import ListingRecommendationService
    from app.services.recommendation_explanation_service import RecommendationExplanationService
    from app.services.listing_insights_service import ListingInsightsService
    settings=Settings.from_environment()
    try: settings.require_complete()
    except ConfigurationError: raise HTTPException(503,"Amazon listing connection is not configured") from None
    repository=ListingSnapshotRepository(); intelligence=ListingIntelligenceService(repository)
    return ListingInsightsService(repository,intelligence,ListingRecommendationService(),RecommendationExplanationService.from_environment()).get_insights(settings.seller_id or "",settings.marketplace_id or "",asin,window).public_dict()
