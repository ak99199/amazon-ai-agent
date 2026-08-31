"""Authenticated, read-only Ads readiness, diagnostics, and recommendations endpoints."""
import os
from fastapi import APIRouter, HTTPException, Query
from app.config import ConfigurationError, require_dashboard_context
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_diagnostics_service import AdsDiagnosticsService
from app.services.ads_readiness_service import AdsReadinessService
from app.services.ads_recommendation_service import AdsRecommendationService
from app.services.ads_signal_service import AdsRecommendationConfigurationError

router = APIRouter(prefix="/api/ads", tags=["ads"])


def _services():
    repository = AdsPerformanceRepository()
    diagnostics = AdsDiagnosticsService(repository)
    return repository, diagnostics, AdsReadinessService(diagnostics)


def _context():
    return require_dashboard_context()


@router.get("/readiness")
def readiness():
    try:
        context = _context()
        _, _, service = _services()
        return service.get(context.seller_id, context.marketplace_id).public_dict()
    except (ConfigurationError, Exception):
        raise HTTPException(503, "Ads status is unavailable") from None


@router.get("/diagnostics")
def diagnostics():
    try:
        context = _context()
        _, service, _ = _services()
        return service.get(context.seller_id, context.marketplace_id, os.getenv("AMAZON_ADS_PROFILE_ID"))
    except (ConfigurationError, Exception):
        raise HTTPException(503, "Ads diagnostics are unavailable") from None


@router.get("/ingestion-runs")
def ingestion_runs(limit: int = Query(20, ge=1, le=100)):
    try:
        context = _context()
        profile_id = os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:
            return {"runs": []}
        repository, _, _ = _services()
        rows = repository.list_ingestion_runs(context.seller_id, context.marketplace_id, profile_id, limit)
        fields = ("run_id", "profile_id", "started_at", "finished_at", "success", "campaigns_fetched", "keywords_fetched", "targets_fetched", "report_rows_received", "rows_normalized", "rows_saved", "rows_failed")
        return {"runs": [{field: row[field] for field in fields} for row in rows]}
    except (ConfigurationError, Exception):
        raise HTTPException(503, "Ads diagnostics are unavailable") from None


@router.get("/recommendations")
def recommendations(
    window: int = Query(30),
    scope_type: str | None = Query(None),
    campaign_id: str | None = Query(None),
    keyword_id: str | None = Query(None),
    search_term: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    if window not in AdsRecommendationService.allowed_windows:
        raise HTTPException(422, "Unsupported Ads recommendation window")
    if scope_type not in (None, "campaign", "keyword", "search_term"):
        raise HTTPException(422, "Unsupported Ads recommendation scope")
    if priority not in (None, "low", "medium", "high", "critical"):
        raise HTTPException(422, "Unsupported Ads recommendation priority")
    try:
        context = _context()
        profile_id = os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:
            return {"recommendations": [], "count": 0, "window": window}
        repository, _, _ = _services()
        records = AdsRecommendationService(repository).get_recommendations(
            context.seller_id, context.marketplace_id, profile_id, window, scope_type,
            campaign_id, keyword_id, search_term, priority,
        )
        public = [record.public_dict() for record in records[:limit]]
        return {"recommendations": public, "count": len(public), "window": window}
    except AdsRecommendationConfigurationError:
        raise HTTPException(503, "Ads recommendations are unavailable") from None
    except (ConfigurationError, Exception):
        raise HTTPException(503, "Ads recommendations are unavailable") from None