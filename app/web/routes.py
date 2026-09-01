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
from app.services.ads_execution_plan_service import AdsExecutionPlanService
from app.services.ads_sync_gate_service import AdsSyncGateService
from app.services.ads_manual_sync_service import AdsManualSyncService
from app.services.ads_sync_observability_service import AdsSyncObservabilityService
from app.services.ads_intelligence_service import AdsIntelligenceService
from app.services.ads_recommendation_effectiveness_service import AdsRecommendationEffectivenessService
from app.services.ads_rule_tuning_proposal_service import AdsRuleTuningProposalService
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
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
def _ads_execution_plans(context):
 try:
  profile_id=getenv("AMAZON_ADS_PROFILE_ID")
  if not profile_id:return {"plans":[],"unavailable":False}
  repository=AdsPerformanceRepository();return {"plans":AdsExecutionPlanService(AdsRecommendationService(repository),repository).list_plans(context.seller_id,context.marketplace_id,profile_id,5),"unavailable":False}
 except Exception:return {"plans":[],"unavailable":True}
def _ads_sync(context):
 try:
  repository=AdsPerformanceRepository();service=AdsManualSyncService(AdsSyncGateService(AdsSettings.from_environment(),repository,AdsLiveReadConfig.from_environment()),repository)
  return {**service.status(context.seller_id,context.marketplace_id),"unavailable":False}
 except Exception:return {"gate":{"allowed":False,"mode":None,"status_code":"error","status_message":"Ads sync unavailable."},"latest_sync":None,"unavailable":True}
def _ads_sync_health(context):
 try:
  repository=AdsPerformanceRepository();gate=AdsSyncGateService(AdsSettings.from_environment(),repository,AdsLiveReadConfig.from_environment());return {**AdsSyncObservabilityService(repository,gate).get(context.seller_id,context.marketplace_id).public_dict(),"unavailable":False}
 except Exception:return {"health_status":"error","recent_runs":[],"unavailable":True}
def _ads_intelligence(context, window=30):
 try:
  repository=AdsPerformanceRepository();profile_id=AdsSettings.from_environment().profile_id
  return {**AdsIntelligenceService(repository).get(context.seller_id,context.marketplace_id,profile_id,window,5).public_dict(),"unavailable":False}
 except Exception:return {"summary":{"totals":{}},"trend":[],"top_campaigns":[],"weak_campaigns":[],"top_keywords":[],"weak_keywords":[],"profitable_search_terms":[],"wasted_search_terms":[],"recommendations":{"total":0,"by_code":{}},"decisions":{"pending":0,"approved":0,"rejected":0,"dismissed":0,"approved_is_not_executed":True},"sync_health":{"health_status":"unavailable"},"unavailable":True}
def _ads_effectiveness(context):
 try:
  repository=AdsPerformanceRepository();profile_id=AdsSettings.from_environment().profile_id
  return {**AdsRecommendationEffectivenessService(repository).get(context.seller_id,context.marketplace_id,profile_id,30).public_dict(),"unavailable":False}
 except Exception:return {"total_reviewed":0,"total_approved":0,"total_rejected":0,"total_dismissed":0,"approval_rate":None,"rejection_rate":None,"by_code":[],"repeated_rejection_codes":[],"high_approval_codes":[],"unavailable":True}
def _ads_rule_tuning(context):
 try:
  repo=AdsPerformanceRepository();profile=AdsSettings.from_environment().profile_id
  return {**AdsRuleTuningProposalService(repo,AdsRecommendationEffectivenessService(repo)).generate(context.seller_id,context.marketplace_id,profile),"unavailable":False}
 except Exception:return {"baseline":None,"proposals":[],"evaluation":{},"unavailable":True}
def _recent_alerts(context):
 try:
  repository=create_alert_repository();return repository.count_alerts(context.seller_id,context.marketplace_id,"new"),[item.public_dict() for item in repository.list_alerts(context.seller_id,context.marketplace_id,limit=5)]
 except Exception:return 0,[]
@router.get("/dashboard",response_class=HTMLResponse)
def dashboard(request:Request,window:str="30",sort:str="risk_desc",priority:str|None=None,status:str|None=None,confidence:str|None=None,risk_level:str|None=None,changed_recently:bool|None=None,needs_attention:bool=False):
 try:
  context,(repo,portfolio,_)=_context();data=portfolio.get_portfolio(context.seller_id,context.marketplace_id,window,sort,priority,status,confidence,changed_recently,None,200).public_dict();data["listings"]=_apply_ui_filters(data["listings"],risk_level,needs_attention);attention=sum(row["priority"] in ("critical","high") for row in data["listings"]);actions=sorted(data["listings"],key=lambda row:({"critical":0,"high":1,"medium":2,"low":3}.get(row["priority"],4),-row["risk_score"],row["asin"]));new_alert_count,recent_alerts=_recent_alerts(context);ads_readiness=_ads_readiness(context);ads_recommendations=_ads_recommendations(context);ads_actions=_ads_actions(context);ads_execution_plans=_ads_execution_plans(context);ads_sync=_ads_sync(context);ads_sync_health=_ads_sync_health(context);ads_intelligence=_ads_intelligence(context,int(window) if window.isdigit() and int(window) in AdsIntelligenceService.allowed_windows else 30);ads_effectiveness=_ads_effectiveness(context);ads_rule_tuning=_ads_rule_tuning(context);error=None
 except Exception:data=_empty();actions=[];attention=0;new_alert_count=0;recent_alerts=[];ads_readiness={"overall_status":"error","unavailable":True};ads_recommendations={"recommendations":[],"count":0,"high_count":0,"unavailable":True};ads_actions={"actions":[],"count":0,"pending_count":0,"approved_count":0,"rejected_count":0,"dismissed_count":0,"unavailable":True};ads_execution_plans={"plans":[],"unavailable":True};ads_sync={"gate":{"allowed":False,"mode":None,"status_code":"error","status_message":"Ads sync unavailable."},"latest_sync":None,"unavailable":True};ads_sync_health={"health_status":"error","recent_runs":[],"unavailable":True};ads_intelligence=_ads_intelligence(context,30) if "context" in locals() else {"summary":{"totals":{}},"trend":[],"top_campaigns":[],"weak_campaigns":[],"top_keywords":[],"weak_keywords":[],"profitable_search_terms":[],"wasted_search_terms":[],"recommendations":{"total":0,"by_code":{}},"decisions":{"pending":0,"approved":0,"rejected":0,"dismissed":0,"approved_is_not_executed":True},"sync_health":{"health_status":"unavailable"},"unavailable":True};ads_effectiveness={"total_reviewed":0,"total_approved":0,"total_rejected":0,"total_dismissed":0,"approval_rate":None,"rejection_rate":None,"by_code":[],"repeated_rejection_codes":[],"high_approval_codes":[],"unavailable":True};ads_rule_tuning={"baseline":None,"proposals":[],"evaluation":{},"unavailable":True};error="Listing history is not configured or is not available yet."
 return templates.TemplateResponse(request,"dashboard.html",{"portfolio":data,"actions":actions,"needs_attention":attention,"new_alert_count":new_alert_count,"recent_alerts":recent_alerts,"ads_readiness":ads_readiness,"ads_recommendations":ads_recommendations,"ads_actions":ads_actions,"ads_execution_plans":ads_execution_plans,"ads_sync":ads_sync,"ads_sync_health":ads_sync_health,"ads_intelligence":ads_intelligence,"ads_effectiveness":ads_effectiveness,"ads_rule_tuning":ads_rule_tuning,"error":error,"window":window,"sort":sort,"priority":priority or "","status":status or "","confidence":confidence or "","risk_level":risk_level or "","changed_recently":changed_recently,"csrf_token":csrf_token(request)})
@router.get("/dashboard/listings/{asin}",response_class=HTMLResponse)
def listing_detail(request:Request,asin:str,window:str="30"):
 try:
  context,(repo,_,insights)=_context();data=insights.get_insights(context.seller_id,context.marketplace_id,asin,window).public_dict();data["history"]=[snapshot.public_dict() for snapshot in repo.get_listing_history(context.seller_id,context.marketplace_id,asin,10)];error=None
 except Exception:data={"current_listing":None,"history_summary":{},"intelligence":{},"recommendations":{"recommendations":[]},"explanation":{},"history":[]};error="Listing insight data is not available."
 return templates.TemplateResponse(request,"listing.html",{"insights":data,"error":error,"asin":asin,"action_labels":ACTION_LABELS,"csrf_token":csrf_token(request)})