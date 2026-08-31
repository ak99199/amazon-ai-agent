from os import getenv
from pathlib import Path
from fastapi import APIRouter,Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.alerts.repository import create_alert_repository
from app.config import require_dashboard_context
from app.database.ads_repository import AdsPerformanceRepository
from app.database.base import create_snapshot_repository
from app.services.ads_diagnostics_service import AdsDiagnosticsService
from app.services.ads_readiness_service import AdsReadinessService
from app.services.ads_recommendation_service import AdsRecommendationService
from app.services.ads_action_service import AdsActionService
from app.services.listing_intelligence_service import ListingIntelligenceService
from app.services.listing_recommendation_service import ListingRecommendationService
from app.services.recommendation_explanation_service import RecommendationExplanationService
from app.services.listing_insights_service import ListingInsightsService
from app.services.portfolio_insights_service import PortfolioInsightsService
from app.security.auth import csrf_token
router=APIRouter();templates=Jinja2Templates(directory=str(Path(__file__).resolve().parents[2]/"templates"))
ACTION_LABELS={"KEEP_STABLE":"Keep Listing Stable","WAIT_FOR_MORE_DATA":"Wait for More History","REVIEW_TITLE":"Review Product Title","CHECK_LISTING_STATUS":"Check Listing Status","REVIEW_PRICE_VOLATILITY":"Review Price Changes","REVIEW_FULFILLMENT":"Review Fulfillment Setup","INVESTIGATE_RECENT_CHANGE":"Investigate Recent Change","MONITOR_LISTING":"Continue Monitoring","REVIEW_LISTING_QUALITY":"Review Listing Quality"}
templates.env.globals["action_label"]=lambda value:ACTION_LABELS.get(value,value.replace("_"," ").title())
def _services():
 repo=create_snapshot_repository();intelligence=ListingIntelligenceService(repo);insights=ListingInsightsService(repo,intelligence,ListingRecommendationService(),RecommendationExplanationService.from_environment());return repo,PortfolioInsightsService(repo,insights),insights
def _context():return require_dashboard_context(),_services()
def _empty():return {"total_listings":0,"active_listings":0,"inactive_listings":0,"high_risk_count":0,"medium_risk_count":0,"low_risk_count":0,"stable_count":0,"recently_changed_count":0,"insufficient_history_count":0,"average_risk_score":0,"average_opportunity_score":0,"average_stability_score":0,"listings":[]}
def _apply_ui_filters(rows,risk_level,needs_attention):
 if risk_level:
  ranges={"high":lambda x:x["risk_score"]>=70,"medium":lambda x:30<=x["risk_score"]<70,"low":lambda x:x["risk_score"]<30};rows=[row for row in rows if risk_level in ranges and ranges[risk_level](row)]
 if needs_attention:rows=[row for row in rows if row["priority"] in ("critical","high")]
 return rows
def _ads_readiness(context):
 try:return AdsReadinessService(AdsDiagnosticsService(AdsPerformanceRepository())).get(context.seller_id,context.marketplace_id).public_dict()
 except Exception:return {"overall_status":"error","approval_status":"unknown","config_status":"unavailable","profile_status":"unavailable","data_status":"unavailable","ingestion_run_count":0,"last_ingestion_at":None,"unavailable":True}
def _ads_recommendations(context):
 try:
  profile_id=getenv("AMAZON_ADS_PROFILE_ID")
  if not profile_id:return {"recommendations":[],"count":0,"high_count":0,"unavailable":False}
  records=AdsRecommendationService(AdsPerformanceRepository()).get_recommendations(context.seller_id,context.marketplace_id,profile_id,30)
  public=[item.public_dict() for item in records]
  return {"recommendations":public[:5],"count":len(public),"high_count":sum(item["priority"] in ("critical","high") for item in public),"unavailable":False}
 except Exception:return {"recommendations":[],"count":0,"high_count":0,"unavailable":True}
def _ads_actions(context):
 try:
  profile_id=getenv("AMAZON_ADS_PROFILE_ID")
  if not profile_id:return {"actions":[],"count":0,"pending_count":0,"approved_count":0,"rejected_count":0,"dismissed_count":0,"unavailable":False}
  repository=AdsPerformanceRepository();return {**AdsActionService(AdsRecommendationService(repository),repository).list_actions(context.seller_id,context.marketplace_id,profile_id,30,limit=5),"unavailable":False}
 except Exception:return {"actions":[],"count":0,"pending_count":0,"approved_count":0,"rejected_count":0,"dismissed_count":0,"unavailable":True}
def _recent_alerts(context):
 try:
  repository=create_alert_repository();return repository.count_alerts(context.seller_id,context.marketplace_id,"new"),[item.public_dict() for item in repository.list_alerts(context.seller_id,context.marketplace_id,limit=5)]
 except Exception:return 0,[]
@router.get("/dashboard",response_class=HTMLResponse)
def dashboard(request:Request,window:str="30",sort:str="risk_desc",priority:str|None=None,status:str|None=None,confidence:str|None=None,risk_level:str|None=None,changed_recently:bool|None=None,needs_attention:bool=False):
 try:
  context,(repo,portfolio,_)=_context();data=portfolio.get_portfolio(context.seller_id,context.marketplace_id,window,sort,priority,status,confidence,changed_recently,None,200).public_dict();data["listings"]=_apply_ui_filters(data["listings"],risk_level,needs_attention);attention=sum(row["priority"] in ("critical","high") for row in data["listings"]);actions=sorted(data["listings"],key=lambda row:({"critical":0,"high":1,"medium":2,"low":3}.get(row["priority"],4),-row["risk_score"],row["asin"]));new_alert_count,recent_alerts=_recent_alerts(context);ads_readiness=_ads_readiness(context);ads_recommendations=_ads_recommendations(context);ads_actions=_ads_actions(context);error=None
 except Exception:data=_empty();actions=[];attention=0;new_alert_count=0;recent_alerts=[];ads_readiness={"overall_status":"error","unavailable":True};ads_recommendations={"recommendations":[],"count":0,"high_count":0,"unavailable":True};ads_actions={"actions":[],"count":0,"pending_count":0,"approved_count":0,"rejected_count":0,"dismissed_count":0,"unavailable":True};error="Listing history is not configured or is not available yet."
 return templates.TemplateResponse(request,"dashboard.html",{"portfolio":data,"actions":actions,"needs_attention":attention,"new_alert_count":new_alert_count,"recent_alerts":recent_alerts,"ads_readiness":ads_readiness,"ads_recommendations":ads_recommendations,"ads_actions":ads_actions,"error":error,"window":window,"sort":sort,"priority":priority or "","status":status or "","confidence":confidence or "","risk_level":risk_level or "","changed_recently":changed_recently,"csrf_token":csrf_token(request)})
@router.get("/dashboard/listings/{asin}",response_class=HTMLResponse)
def listing_detail(request:Request,asin:str,window:str="30"):
 try:
  context,(repo,_,insights)=_context();data=insights.get_insights(context.seller_id,context.marketplace_id,asin,window).public_dict();data["history"]=[snapshot.public_dict() for snapshot in repo.get_listing_history(context.seller_id,context.marketplace_id,asin,10)];error=None
 except Exception:data={"current_listing":None,"history_summary":{},"intelligence":{},"recommendations":{"recommendations":[]},"explanation":{},"history":[]};error="Listing insight data is not available."
 return templates.TemplateResponse(request,"listing.html",{"insights":data,"error":error,"asin":asin,"action_labels":ACTION_LABELS,"csrf_token":csrf_token(request)})
