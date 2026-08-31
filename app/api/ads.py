"""Authenticated Ads visibility and internal human-review endpoints; no Ads execution."""
import os
from fastapi import APIRouter, HTTPException, Query
from datetime import date
from pydantic import BaseModel, Field
from app.config import ConfigurationError, require_dashboard_context
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_action_service import AdsActionService, UnknownAdsRecommendationError
from app.services.ads_execution_plan_service import AdsExecutionPlanService, UnknownAdsExecutionRecommendationError
from app.services.ads_execution_safety_service import AdsExecutionSafetyConfigurationError
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.auth import AdsLwaAuthenticator
from app.amazon_ads.client import AmazonAdsClient
from app.amazon_ads.profiles import AdsProfilesService
from app.amazon_ads.read_adapters import SponsoredProductsReadAdapter
from app.services.ads_live_read_service import AdsLiveReadService, AdsLiveReadBlockedError
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.services.ads_sync_gate_service import AdsSyncGateService
from app.services.ads_manual_sync_service import AdsManualSyncService
from app.services.ads_diagnostics_service import AdsDiagnosticsService
from app.services.ads_readiness_service import AdsReadinessService
from app.services.ads_recommendation_service import AdsRecommendationService
from app.services.ads_signal_service import AdsRecommendationConfigurationError

router = APIRouter(prefix="/api/ads", tags=["ads"])


class DecisionRequest(BaseModel):
    status: str
    review_note: str | None = Field(default=None, max_length=1000)


def _services():
    repository = AdsPerformanceRepository()
    diagnostics = AdsDiagnosticsService(repository)
    return repository, diagnostics, AdsReadinessService(diagnostics)


def _context():
    return require_dashboard_context()


def _action_service(repository):
    return AdsActionService(AdsRecommendationService(repository), repository)


@router.get("/readiness")
def readiness():
    try:
        context = _context(); _, _, service = _services()
        return service.get(context.seller_id, context.marketplace_id).public_dict()
    except (ConfigurationError, Exception):
        raise HTTPException(503, "Ads status is unavailable") from None


@router.get("/diagnostics")
def diagnostics():
    try:
        context = _context(); _, service, _ = _services()
        return service.get(context.seller_id, context.marketplace_id, os.getenv("AMAZON_ADS_PROFILE_ID"))
    except (ConfigurationError, Exception):
        raise HTTPException(503, "Ads diagnostics are unavailable") from None


@router.get("/ingestion-runs")
def ingestion_runs(limit: int = Query(20, ge=1, le=100)):
    try:
        context = _context(); profile_id = os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:
            return {"runs": []}
        repository, _, _ = _services(); rows = repository.list_ingestion_runs(context.seller_id, context.marketplace_id, profile_id, limit)
        fields = ("run_id", "profile_id", "started_at", "finished_at", "success", "campaigns_fetched", "keywords_fetched", "targets_fetched", "report_rows_received", "rows_normalized", "rows_saved", "rows_failed")
        return {"runs": [{field: row[field] for field in fields} for row in rows]}
    except (ConfigurationError, Exception):
        raise HTTPException(503, "Ads diagnostics are unavailable") from None


@router.get("/recommendations")
def recommendations(window: int = Query(30), scope_type: str | None = Query(None), campaign_id: str | None = Query(None), keyword_id: str | None = Query(None), search_term: str | None = Query(None), priority: str | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    if window not in AdsRecommendationService.allowed_windows:
        raise HTTPException(422, "Unsupported Ads recommendation window")
    if scope_type not in (None, "campaign", "keyword", "search_term") or priority not in (None, "low", "medium", "high", "critical"):
        raise HTTPException(422, "Unsupported Ads recommendation filter")
    try:
        context = _context(); profile_id = os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:
            return {"recommendations": [], "count": 0, "window": window}
        repository, _, _ = _services()
        records = AdsRecommendationService(repository).get_recommendations(context.seller_id, context.marketplace_id, profile_id, window, scope_type, campaign_id, keyword_id, search_term, priority)
        public = [record.public_dict() for record in records[:limit]]
        return {"recommendations": public, "count": len(public), "window": window}
    except AdsRecommendationConfigurationError:
        raise HTTPException(503, "Ads recommendations are unavailable") from None
    except (ConfigurationError, Exception):
        raise HTTPException(503, "Ads recommendations are unavailable") from None


@router.get("/actions")
def actions(window: int = Query(30), status: str | None = Query(None), priority: str | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    if window not in AdsRecommendationService.allowed_windows or status not in (None, "pending", "approved", "rejected", "dismissed") or priority not in (None, "low", "medium", "high", "critical"):
        raise HTTPException(422, "Unsupported Ads action filter")
    try:
        context = _context(); profile_id = os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:
            return {"actions": [], "count": 0, "pending_count": 0, "approved_count": 0, "rejected_count": 0, "dismissed_count": 0, "window": window}
        repository, _, _ = _services()
        return _action_service(repository).list_actions(context.seller_id, context.marketplace_id, profile_id, window, status, priority, limit)
    except (ConfigurationError, AdsRecommendationConfigurationError, ValueError):
        raise HTTPException(503, "Ads Action Center is unavailable") from None
    except Exception:
        raise HTTPException(503, "Ads Action Center is unavailable") from None


@router.post("/actions/{recommendation_id}/decision")
def decide(recommendation_id: str, payload: DecisionRequest):
    try:
        context = _context(); profile_id = os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:
            raise HTTPException(404, "Ads recommendation is not available")
        repository, _, _ = _services()
        decision = _action_service(repository).set_decision(context.seller_id, context.marketplace_id, profile_id, recommendation_id, payload.status, payload.review_note)
        return decision.public_dict()
    except UnknownAdsRecommendationError:
        raise HTTPException(404, "Ads recommendation is not available") from None
    except ValueError:
        raise HTTPException(422, "Invalid Ads review decision") from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Ads Action Center is unavailable") from None

@router.get("/execution-plans")
def execution_plans(limit: int = Query(50, ge=1, le=200)):
    try:
        context = _context(); profile_id = os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id: return {"plans": [], "count": 0}
        repository, _, _ = _services()
        plans = AdsExecutionPlanService(AdsRecommendationService(repository), repository).list_plans(context.seller_id, context.marketplace_id, profile_id, limit)
        return {"plans": plans, "count": len(plans)}
    except Exception:
        raise HTTPException(503, "Execution planning is unavailable") from None


@router.post("/actions/{recommendation_id}/dry-run")
def dry_run(recommendation_id: str, window: int = Query(30)):
    if window not in AdsRecommendationService.allowed_windows:
        raise HTTPException(422, "Unsupported Ads recommendation window")
    try:
        context = _context(); profile_id = os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id: raise HTTPException(404, "Ads recommendation is not available")
        repository, _, _ = _services()
        plan = AdsExecutionPlanService(AdsRecommendationService(repository), repository).create_dry_run(context.seller_id, context.marketplace_id, profile_id, recommendation_id, window)
        return plan.public_dict()
    except UnknownAdsExecutionRecommendationError:
        raise HTTPException(404, "Ads recommendation is not available") from None
    except AdsExecutionSafetyConfigurationError:
        raise HTTPException(503, "Execution planning is unavailable") from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Execution planning is unavailable") from None


def _live_read_service():
    settings=AdsSettings.from_environment()
    service=AdsLiveReadService(settings)
    if not service.status().ready:
        return service
    client=AmazonAdsClient(settings,AdsLwaAuthenticator(settings))
    return AdsLiveReadService(settings,AdsProfilesService(client),SponsoredProductsReadAdapter(client))


@router.get("/live-read/status")
def live_read_status():
    try:
        return _live_read_service().status().public_dict()
    except Exception:
        return {"mode":"configuration_error","live_read_enabled":False,"mock_data_enabled":True,"approval_status":"unknown","config_complete":False,"profile_selected":False,"ready":False,"last_error_code":"configuration_error"}


@router.get("/live-read/profiles")
def live_read_profiles():
    try:
        service=_live_read_service(); status=service.status()
        if not status.ready:
            return {"status":status.public_dict(),"profiles":[]}
        return {"status":status.public_dict(),"profiles":[profile.public_dict() for profile in service.discover_profiles()]}
    except AdsLiveReadBlockedError:
        return {"status":live_read_status(),"profiles":[]}
    except Exception:
        raise HTTPException(503,"Live Ads read is unavailable") from None

class SyncRequest(BaseModel):
    window_days: int = Field(default=7, ge=1, le=90)
    start_date: date | None = None
    end_date: date | None = None


def _sync_service(repository):
    settings=AdsSettings.from_environment()
    gate=AdsSyncGateService(settings,repository,AdsLiveReadConfig.from_environment())
    return AdsManualSyncService(gate,repository)


@router.get("/sync/status")
def sync_status():
    try:
        context=_context(); repository,_,_=_services()
        return _sync_service(repository).status(context.seller_id,context.marketplace_id)
    except Exception:
        raise HTTPException(503,"Ads sync is unavailable") from None


@router.get("/sync-runs")
def sync_runs(limit:int=Query(20,ge=1,le=100)):
    try:
        context=_context(); repository,_,_= _services(); profile_id=AdsSettings.from_environment().profile_id
        return {"runs":[item.public_dict() for item in repository.list_sync_runs(context.seller_id,context.marketplace_id,profile_id,limit)]}
    except Exception:
        raise HTTPException(503,"Ads sync is unavailable") from None


@router.post("/sync")
def sync(payload: SyncRequest):
    try:
        context=_context(); repository,_,_= _services()
        result=_sync_service(repository).run(context.seller_id,context.marketplace_id,start_date=payload.start_date,end_date=payload.end_date,window_days=payload.window_days)
        return result.public_dict()
    except ValueError:
        raise HTTPException(422,"Invalid Ads sync date range") from None
    except Exception:
        raise HTTPException(503,"Ads sync is unavailable") from None