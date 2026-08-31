from pathlib import Path
from fastapi import APIRouter,Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.config import Settings,ConfigurationError
from app.database.base import create_snapshot_repository
from app.services.listing_intelligence_service import ListingIntelligenceService
from app.services.listing_recommendation_service import ListingRecommendationService
from app.services.recommendation_explanation_service import RecommendationExplanationService
from app.services.listing_insights_service import ListingInsightsService
from app.services.portfolio_insights_service import PortfolioInsightsService
from app.security.auth import csrf_token
router=APIRouter()
templates=Jinja2Templates(directory=str(Path(__file__).resolve().parents[2]/"templates"))
def _services():
    repo=create_snapshot_repository(); intelligence=ListingIntelligenceService(repo); insights=ListingInsightsService(repo,intelligence,ListingRecommendationService(),RecommendationExplanationService.from_environment()); return PortfolioInsightsService(repo,insights),insights
def _context():
    settings=Settings.from_environment(); settings.require_complete(); return settings,_services()
def _empty(): return {"total_listings":0,"active_listings":0,"inactive_listings":0,"high_risk_count":0,"medium_risk_count":0,"low_risk_count":0,"stable_count":0,"recently_changed_count":0,"insufficient_history_count":0,"average_risk_score":0,"average_opportunity_score":0,"average_stability_score":0,"listings":[]}
@router.get("/dashboard",response_class=HTMLResponse)
def dashboard(request:Request,window:str="30",sort:str="risk_desc",priority:str|None=None,status:str|None=None,confidence:str|None=None):
    try:
        settings,(portfolio,_)=_context(); data=portfolio.get_portfolio(settings.seller_id or "",settings.marketplace_id or "",window,sort,priority,status,confidence,limit=200).public_dict(); error=None
    except (ConfigurationError,ValueError): data=_empty(); error="Listing history is not configured or is not available yet."
    return templates.TemplateResponse(request,"dashboard.html",{"portfolio":data,"error":error,"window":window,"sort":sort,"priority":priority or "","status":status or "","confidence":confidence or "","csrf_token":csrf_token(request)})
@router.get("/dashboard/listings/{asin}",response_class=HTMLResponse)
def listing_detail(request:Request,asin:str,window:str="30"):
    try:
        settings,(_,insights)=_context(); data=insights.get_insights(settings.seller_id or "",settings.marketplace_id or "",asin,window).public_dict(); error=None
    except (ConfigurationError,ValueError): data={"current_listing":None,"history_summary":{},"intelligence":{},"recommendations":{"recommendations":[]},"explanation":{}}; error="Listing insight data is not available."
    return templates.TemplateResponse(request,"listing.html",{"insights":data,"error":error,"asin":asin})


