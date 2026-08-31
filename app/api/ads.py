"""Authenticated, read-only Ads readiness and diagnostics endpoints."""
from fastapi import APIRouter,HTTPException,Query
from app.config import ConfigurationError,require_dashboard_context
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_diagnostics_service import AdsDiagnosticsService
from app.services.ads_readiness_service import AdsReadinessService
router=APIRouter(prefix="/api/ads",tags=["ads"])
def _services():return AdsDiagnosticsService(AdsPerformanceRepository()),AdsReadinessService(AdsDiagnosticsService(AdsPerformanceRepository()))
def _context():return require_dashboard_context()
@router.get("/readiness")
def readiness():
    try:context=_context();_,service=_services();return service.get(context.seller_id,context.marketplace_id).public_dict()
    except (ConfigurationError,Exception):raise HTTPException(503,"Ads status is unavailable") from None
@router.get("/diagnostics")
def diagnostics():
    try:context=_context();service,_=_services();return service.get(context.seller_id,context.marketplace_id,__import__("os").getenv("AMAZON_ADS_PROFILE_ID"))
    except (ConfigurationError,Exception):raise HTTPException(503,"Ads diagnostics are unavailable") from None
@router.get("/ingestion-runs")
def ingestion_runs(limit:int=Query(20,ge=1,le=100)):
    try:
        context=_context();profile_id=__import__("os").getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:return {"runs":[]}
        rows=AdsPerformanceRepository().list_ingestion_runs(context.seller_id,context.marketplace_id,profile_id,limit);fields=("run_id","profile_id","started_at","finished_at","success","campaigns_fetched","keywords_fetched","targets_fetched","report_rows_received","rows_normalized","rows_saved","rows_failed");return {"runs":[{field:row[field] for field in fields} for row in rows]}
    except (ConfigurationError,Exception):raise HTTPException(503,"Ads diagnostics are unavailable") from None