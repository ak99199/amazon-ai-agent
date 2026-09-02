"""Authenticated Ads visibility and internal human-review endpoints; no Ads execution."""
import os
from fastapi import APIRouter, HTTPException, Query
from datetime import date, datetime, timezone
from pydantic import BaseModel, Field
from app.config import ConfigurationError, require_dashboard_context
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_action_service import AdsActionService, UnknownAdsRecommendationError
from app.services.ads_execution_plan_service import AdsExecutionPlanService, UnknownAdsExecutionRecommendationError
from app.services.ads_write_preflight_service import AdsWritePreflightService
from app.amazon_ads.write_models import AdsWriteConfig
from app.services.ads_exact_value_proposal_service import AdsExactValueProposalService
from app.services.ads_write_intent_service import AdsWriteIntentService
from app.services.ads_write_intent_revalidation_service import AdsWriteIntentRevalidationService
from app.services.ads_write_target_resolution_service import AdsWriteTargetResolutionService
from app.amazon_ads.write_intent_models import AdsWriteIntentBlockedError
from app.services.ads_execution_safety_service import AdsExecutionSafetyConfigurationError
from app.amazon_ads.config import AdsScheduledSyncConfig,AdsSettings
from app.amazon_ads.auth import AdsLwaAuthenticator
from app.amazon_ads.client import AmazonAdsClient
from app.amazon_ads.profiles import AdsProfilesService
from app.amazon_ads.read_adapters import SponsoredProductsReadAdapter
from app.services.ads_live_read_service import AdsLiveReadService, AdsLiveReadBlockedError
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.services.ads_sync_gate_service import AdsSyncGateService
from app.services.ads_manual_sync_service import AdsManualSyncService
from app.services.ads_sync_observability_service import AdsSyncObservabilityService
from app.services.ads_intelligence_service import AdsIntelligenceService
from app.services.ads_recommendation_effectiveness_service import AdsRecommendationEffectivenessService
from app.services.ads_rule_tuning_proposal_service import AdsRuleTuningProposalService
from app.amazon_ads.rule_versions import AdsRuleVersions
from app.services.ads_diagnostics_service import AdsDiagnosticsService
from app.services.ads_readiness_service import AdsReadinessService
from app.services.ads_recommendation_service import AdsRecommendationService
from app.services.ads_signal_service import AdsRecommendationConfigurationError
from app.amazon_ads.rule_activation_models import AdsRuleActivationRequest,AdsRuleRollbackRequest
from app.services.ads_rule_activation_service import AdsRuleActivationService
from app.services.ads_rule_rollback_service import AdsRuleRollbackService
from app.services.ads_rule_version_view_service import AdsRuleVersionViewService
from app.services.ads_production_readiness_service import AdsProductionReadinessService
from app.services.ads_live_smoke_test_service import AdsLiveSmokeTestService
from app.services.ads_live_entity_validation_service import AdsLiveEntityValidationService
from app.services.ads_live_targeting_validation_service import AdsLiveTargetingValidationService
from app.amazon_ads.report_transport import AdsReportTransport
from app.amazon_ads.reporting import SponsoredProductsReportingService
from app.services.ads_live_report_lifecycle_validation_service import AdsLiveReportLifecycleValidationService
from app.services.ads_live_report_download_validation_service import AdsLiveReportDownloadValidationService
from app.services.ads_live_report_persistence_service import AdsLiveReportPersistenceService
from app.services.ads_manual_historical_sync_service import AdsManualHistoricalSyncService,HISTORICAL_SYNC_MODE
from app.services.ads_historical_sync_health_service import AdsHistoricalSyncHealthService
from app.services.ads_scheduled_sync_health_service import AdsScheduledSyncHealthService
from app.services.ads_sync_recovery_service import AdsSyncRecoveryService

router = APIRouter(prefix="/api/ads", tags=["ads"])


class RuleTuningDecisionRequest(BaseModel):
    status: str
class RuleVersionChangeRequest(BaseModel):
    confirm: bool = False
    expected_active_rule_version_id: str | None = None
class LiveSmokeTestRequest(BaseModel):
    confirm_live_read: bool = False
class WritePreflightRequest(BaseModel):
    confirm_controlled_write_preflight: bool = False
class ExactValueProposalRequest(BaseModel):
    confirm_exact_value_proposal: bool = False
class WriteIntentRequest(BaseModel):
    confirm_prepare_write_intent: bool = False
class WriteIntentRevalidationRequest(BaseModel):
    confirm_revalidation: bool = False
class WriteIntentCancelRequest(BaseModel):
    confirm_cancel_write_intent: bool = False
class WriteTargetResolutionRequest(BaseModel):
    confirm_target_resolution: bool = False
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

def _production_readiness_service():return AdsProductionReadinessService()

def _live_smoke_test_service():
    readiness=_production_readiness_service()
    def adapter_factory():
        settings=readiness.settings;client=AmazonAdsClient(settings,AdsLwaAuthenticator(settings));return SponsoredProductsReadAdapter(client,max_pages=1,page_size=5)
    return AdsLiveSmokeTestService(readiness,adapter_factory,max_records=5)

def _live_entity_validation_service():
    readiness=_production_readiness_service()
    def dependency_factory():
        settings=readiness.settings;client=AmazonAdsClient(settings,AdsLwaAuthenticator(settings));return AdsProfilesService(client),SponsoredProductsReadAdapter(client,max_pages=1,page_size=10)
    return AdsLiveEntityValidationService(readiness,dependency_factory,max_campaigns=10)

def _live_targeting_validation_service():
    readiness=_production_readiness_service()
    def dependency_factory():
        settings=readiness.settings;client=AmazonAdsClient(settings,AdsLwaAuthenticator(settings));return AdsProfilesService(client),SponsoredProductsReadAdapter(client,max_pages=1,page_size=25)
    return AdsLiveTargetingValidationService(readiness,dependency_factory)

def _live_report_lifecycle_validation_service():
    readiness=_production_readiness_service()
    def dependency_factory():
        settings=readiness.settings;client=AmazonAdsClient(settings,AdsLwaAuthenticator(settings));return AdsReportTransport(client,max_attempts=1),SponsoredProductsReportingService()
    return AdsLiveReportLifecycleValidationService(readiness,dependency_factory,max_polls=5)

def _live_report_download_validation_service():
    readiness=_production_readiness_service();reporting=SponsoredProductsReportingService()
    def dependency_factory():
        settings=readiness.settings;client=AmazonAdsClient(settings,AdsLwaAuthenticator(settings));return AdsReportTransport(client,max_attempts=1),reporting
    lifecycle=AdsLiveReportLifecycleValidationService(readiness,dependency_factory,max_polls=5)
    return AdsLiveReportDownloadValidationService(lifecycle,reporting,row_limit=100,compressed_limit=1048576,decompressed_limit=5242880)

def _manual_historical_sync_service(repository,context):
    readiness=_production_readiness_service();reporting=SponsoredProductsReportingService()
    def dependency_factory():
        settings=readiness.settings;client=AmazonAdsClient(settings,AdsLwaAuthenticator(settings));return AdsReportTransport(client,max_attempts=1),reporting
    lifecycle=AdsLiveReportLifecycleValidationService(readiness,dependency_factory,max_polls=5);download=AdsLiveReportDownloadValidationService(lifecycle,reporting,row_limit=100,compressed_limit=1048576,decompressed_limit=5242880);persistence=AdsLiveReportPersistenceService(download,repository,context.seller_id,context.marketplace_id);gate=AdsSyncGateService(readiness.settings,repository,readiness.config,readiness.approval_status)
    now=lambda:datetime.now(timezone.utc);recovery=AdsSyncRecoveryService(repository,AdsScheduledSyncConfig.from_environment().stale_run_after_hours,now)
    return AdsManualHistoricalSyncService(readiness,gate,repository,persistence,now,recovery)

def _historical_sync_health_service(repository):
    settings=AdsSettings.from_environment();gate=AdsSyncGateService(settings,repository,AdsLiveReadConfig.from_environment())
    return AdsHistoricalSyncHealthService(repository,gate)

def _scheduled_sync_health_service(repository):
    return AdsScheduledSyncHealthService(AdsScheduledSyncConfig.from_environment(),_production_readiness_service(),repository,lambda:datetime.now(timezone.utc))

def _rule_scope():
    context=_context();profile_id=os.getenv("AMAZON_ADS_PROFILE_ID")
    if not profile_id:raise HTTPException(503,"Ads rule-version controls are unavailable")
    return context.seller_id,context.marketplace_id,profile_id

def _activation_response(result):
    body={**result.__dict__,"checks":[check.__dict__ for check in result.checks]}
    if result.status in ("activated","already_active"):return body
    if result.status=="conflict":raise HTTPException(409,"Active rule version changed")
    if result.status=="error":raise HTTPException(503,"Rule-version activation is unavailable")
    failed={check.code for check in result.checks if not check.passed}
    if "VERSION_EXISTS" in failed:raise HTTPException(404,"Rule version is not available")
    if "EXPLICIT_CONFIRMATION" in failed:raise HTTPException(400,"Explicit confirmation is required")
    raise HTTPException(422,"Rule version did not pass activation safety checks")

def _rollback_response(result):
    body={**result.__dict__,"checks":[check.__dict__ for check in result.checks]}
    if result.status=="rolled_back":return body
    if result.status=="conflict":raise HTTPException(409,"Active rule version changed")
    if result.status=="no_history":raise HTTPException(422,"No valid rollback history is available")
    if result.status=="error":raise HTTPException(503,"Rule-version rollback is unavailable")
    if any(check.code=="EXPLICIT_CONFIRMATION" and not check.passed for check in result.checks):raise HTTPException(400,"Explicit confirmation is required")
    raise HTTPException(422,"Rule version did not pass rollback safety checks")

@router.get("/rule-versions/active")
def active_rule_version():
    try:
        seller,marketplace,profile=_rule_scope();repository,_,_=_services();return AdsRuleVersionViewService(repository).active(seller,marketplace,profile)
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Ads rule-version controls are unavailable") from None

@router.get("/rule-versions")
def rule_versions(limit:int=Query(100,ge=1,le=200)):
    try:
        seller,marketplace,profile=_rule_scope();repository,_,_=_services();return AdsRuleVersionViewService(repository).history(seller,marketplace,profile,limit)
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Ads rule-version controls are unavailable") from None

@router.get("/rule-versions/{rule_version_id}/diff")
def rule_version_diff(rule_version_id:str):
    try:
        seller,marketplace,profile=_rule_scope();repository,_,_=_services();result=AdsRuleVersionViewService(repository).diff(seller,marketplace,profile,rule_version_id)
        if result is None:raise HTTPException(404,"Rule version is not available")
        return result
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Ads rule-version controls are unavailable") from None

@router.post("/rule-versions/{rule_version_id}/activate")
def activate_rule_version(rule_version_id:str,payload:RuleVersionChangeRequest):
    try:
        seller,marketplace,profile=_rule_scope();repository,_,_=_services();result=AdsRuleActivationService(repository).activate(AdsRuleActivationRequest(seller,marketplace,profile,rule_version_id,payload.expected_active_rule_version_id,payload.confirm));return _activation_response(result)
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Rule-version activation is unavailable") from None

@router.post("/rule-versions/rollback")
def rollback_rule_version(payload:RuleVersionChangeRequest):
    try:
        seller,marketplace,profile=_rule_scope();repository,_,_=_services();result=AdsRuleRollbackService(repository).rollback(AdsRuleRollbackRequest(seller,marketplace,profile,payload.expected_active_rule_version_id,payload.confirm));return _rollback_response(result)
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Rule-version rollback is unavailable") from None


@router.get("/readiness")
def readiness():
    try:
        context = _context(); _, _, service = _services()
        result=service.get(context.seller_id, context.marketplace_id).public_dict();result["production_live_read"]=_production_readiness_service().get().public_dict();return result
    except (ConfigurationError, Exception):
        raise HTTPException(503, "Ads status is unavailable") from None

@router.post("/live-smoke-test")
def live_smoke_test(payload:LiveSmokeTestRequest):
    try:
        _context();result=_live_smoke_test_service().run(payload.confirm_live_read)
        if result.status=="blocked_confirmation":raise HTTPException(400,"Explicit live-read confirmation is required")
        if result.status.startswith("blocked_"):raise HTTPException(422,result.message)
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Amazon Ads live smoke test is unavailable") from None

@router.post("/live-entity-validation")
def live_entity_validation(payload:LiveSmokeTestRequest):
    try:
        _context();result=_live_entity_validation_service().run(payload.confirm_live_read)
        if result.status=="blocked_confirmation":raise HTTPException(400,"Explicit live-read confirmation is required")
        if result.status.startswith("blocked_"):raise HTTPException(422,"Amazon Ads live entity validation is blocked")
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Amazon Ads live entity validation is unavailable") from None

@router.post("/live-targeting-validation")
def live_targeting_validation(payload:LiveSmokeTestRequest):
    try:
        _context();result=_live_targeting_validation_service().run(payload.confirm_live_read)
        if result.status=="blocked_confirmation":raise HTTPException(400,"Explicit live-read confirmation is required")
        if result.status.startswith("blocked_"):raise HTTPException(422,"Amazon Ads live targeting validation is blocked")
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Amazon Ads live targeting validation is unavailable") from None

@router.post("/live-report-lifecycle-validation")
def live_report_lifecycle_validation(payload:LiveSmokeTestRequest):
    try:
        _context();result=_live_report_lifecycle_validation_service().run(payload.confirm_live_read)
        if result.status=="blocked_confirmation":raise HTTPException(400,"Explicit live-read confirmation is required")
        if result.status.startswith("blocked_"):raise HTTPException(422,"Amazon Ads historical report lifecycle validation is blocked")
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Amazon Ads historical report lifecycle validation is unavailable") from None

@router.post("/live-report-download-validation")
def live_report_download_validation(payload:LiveSmokeTestRequest):
    try:
        _context();result=_live_report_download_validation_service().run(payload.confirm_live_read)
        if result.status=="blocked_confirmation":raise HTTPException(400,"Explicit live-read confirmation is required")
        if result.status.startswith("blocked_"):raise HTTPException(422,"Amazon Ads historical report download validation is blocked")
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Amazon Ads historical report download validation is unavailable") from None


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


@router.get("/intelligence")
def intelligence(window: int = Query(30), limit: int = Query(10, ge=1, le=50)):
    if window not in AdsIntelligenceService.allowed_windows:
        raise HTTPException(422, "Unsupported Ads intelligence window")
    try:
        context = _context(); repository, _, _ = _services()
        profile_id = AdsSettings.from_environment().profile_id
        return AdsIntelligenceService(repository).get(context.seller_id, context.marketplace_id, profile_id, window, limit).public_dict()
    except ValueError:
        raise HTTPException(422, "Invalid Ads intelligence request") from None
    except Exception:
        raise HTTPException(503, "Ads intelligence is unavailable") from None

@router.get("/effectiveness")
def effectiveness(window: int = Query(30)):
    if window not in AdsRecommendationEffectivenessService.allowed_windows:
        raise HTTPException(422, "Unsupported Ads effectiveness window")
    try:
        context = _context(); repository, _, _ = _services(); profile_id = AdsSettings.from_environment().profile_id
        return AdsRecommendationEffectivenessService(repository).get(context.seller_id, context.marketplace_id, profile_id, window).public_dict()
    except Exception:
        raise HTTPException(503, "Ads recommendation effectiveness is unavailable") from None


@router.get("/effectiveness/feedback")
def effectiveness_feedback(window: int = Query(30), limit: int = Query(100, ge=1, le=500)):
    if window not in AdsRecommendationEffectivenessService.allowed_windows:
        raise HTTPException(422, "Unsupported Ads effectiveness window")
    try:
        context = _context(); repository, _, _ = _services(); profile_id = AdsSettings.from_environment().profile_id
        return {"feedback": [item.public_dict() for item in AdsRecommendationEffectivenessService(repository).feedback(context.seller_id, context.marketplace_id, profile_id, window, limit)]}
    except ValueError:
        raise HTTPException(422, "Invalid Ads feedback request") from None
    except Exception:
        raise HTTPException(503, "Ads recommendation effectiveness is unavailable") from None

@router.get("/rule-tuning")
def rule_tuning(window: int = Query(90)):
    if window not in (30,60,90): raise HTTPException(422,"Unsupported rule-tuning window")
    try:
        context=_context(); repository,_,_=_services(); profile=AdsSettings.from_environment().profile_id
        effectiveness=AdsRecommendationEffectivenessService(repository)
        return AdsRuleTuningProposalService(repository,effectiveness).generate(context.seller_id,context.marketplace_id,profile,window)
    except Exception: raise HTTPException(503,"Rule tuning analysis unavailable") from None

@router.get("/rule-tuning/proposals")
def rule_tuning_proposals(limit:int=Query(100,ge=1,le=200)):
    try:
        context=_context(); repository,_,_=_services(); profile=AdsSettings.from_environment().profile_id
        fields=("proposal_id","base_rule_version_id","parameter_name","current_value","proposed_value","direction","reason_code","reason_summary","sample_size","confidence","status","evaluation_summary_json","created_at","reviewed_at")
        return {"proposals":[{field:row[field] for field in fields} for row in repository.list_rule_tuning_proposals(context.seller_id,context.marketplace_id,profile,limit)]}
    except Exception: raise HTTPException(503,"Rule tuning analysis unavailable") from None
@router.get("/rule-tuning/versions")
def rule_tuning_versions():
    try:
        context=_context(); profile=AdsSettings.from_environment().profile_id
        return {"baseline": AdsRuleVersions.baseline(context.seller_id,context.marketplace_id,profile).public_dict()}
    except Exception: raise HTTPException(503,"Rule tuning analysis unavailable") from None

@router.post("/rule-tuning/proposals/{proposal_id}/decision")
def rule_tuning_decision(proposal_id:str,payload:RuleTuningDecisionRequest):
    try:
        context=_context();repository,_,_=_services();profile=AdsSettings.from_environment().profile_id
        result=repository.review_rule_tuning_proposal(context.seller_id,context.marketplace_id,profile,proposal_id,payload.status,datetime.now(timezone.utc))
        if result is None: raise HTTPException(404,"Rule tuning proposal is not available")
        return {"proposal_id":proposal_id,"status":result,"active_rules_changed":False}
    except ValueError: raise HTTPException(422,"Invalid rule-tuning decision") from None
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

@router.post("/execution-plans/{execution_plan_id}/preflight")
def write_preflight(execution_plan_id:str,payload:WritePreflightRequest):
    try:
        context=_context();profile_id=os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:raise HTTPException(503,"Controlled Ads write preflight is unavailable")
        repository,_,_=_services();service=AdsWritePreflightService(AdsRecommendationService(repository),repository,AdsWriteConfig.from_environment(),os.getenv("AMAZON_ADS_APPROVAL_STATUS","pending"))
        result=service.preflight(context.seller_id,context.marketplace_id,profile_id,execution_plan_id,payload.confirm_controlled_write_preflight)
        if result.status=="confirmation_required":raise HTTPException(400,"Explicit controlled-write preflight confirmation is required")
        if result.status=="plan_not_found":raise HTTPException(404,"Execution plan is not available")
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Controlled Ads write preflight is unavailable") from None

@router.post("/execution-plans/{execution_plan_id}/value-proposal")
def exact_value_proposal(execution_plan_id:str,payload:ExactValueProposalRequest):
    try:
        context=_context();profile_id=os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:raise HTTPException(503,"Exact-value proposal is unavailable")
        repository,_,_=_services()
        # No production current-value provider exists in this step: fail closed.
        service=AdsExactValueProposalService(AdsRecommendationService(repository),repository)
        result=service.propose(context.seller_id,context.marketplace_id,profile_id,execution_plan_id,payload.confirm_exact_value_proposal)
        if result.proposal_status=="confirmation_required":raise HTTPException(400,"Explicit exact-value proposal confirmation is required")
        if result.proposal_status=="plan_not_found":raise HTTPException(404,"Execution plan is not available")
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Exact-value proposal is unavailable") from None

@router.post("/execution-plans/{execution_plan_id}/write-intent")
def prepare_write_intent(execution_plan_id:str,payload:WriteIntentRequest):
    try:
        context=_context();profile_id=os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:raise HTTPException(503,"Write-intent preparation is unavailable")
        if payload.confirm_prepare_write_intent is not True:raise HTTPException(400,"Explicit write-intent confirmation is required")
        repository,_,_=_services()
        recommendations=AdsRecommendationService(repository)
        proposal=AdsExactValueProposalService(recommendations,repository).propose(
            context.seller_id,context.marketplace_id,profile_id,execution_plan_id,True)
        preflight=AdsWritePreflightService(recommendations,repository,
            AdsWriteConfig.from_environment(),os.getenv("AMAZON_ADS_APPROVAL_STATUS","pending")).preflight(
                context.seller_id,context.marketplace_id,profile_id,execution_plan_id,True,proposal=proposal)
        service=AdsWriteIntentService(AdsRecommendationService(repository),repository,
            AdsWriteConfig.from_environment(),os.getenv("AMAZON_ADS_APPROVAL_STATUS","pending"))
        intent=service.prepare(context.seller_id,context.marketplace_id,profile_id,
            execution_plan_id,payload.confirm_prepare_write_intent,proposal,preflight)
        return intent.public_dict()
    except AdsWriteIntentBlockedError as error:
        if error.status=="confirmation_required":raise HTTPException(400,"Explicit write-intent confirmation is required") from None
        if error.status=="plan_not_found":raise HTTPException(404,"Execution plan is not available") from None
        return {"status":error.status,"prepared":False,"message":"No Amazon Ads change has been sent."}
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Write-intent preparation is unavailable") from None

@router.get("/write-intents")
def write_intents(status:str|None=Query(None),limit:int=Query(50,ge=1,le=200)):
    try:
        context=_context();profile_id=os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:return {"write_intents":[],"count":0}
        repository,_,_=_services()
        records=AdsWriteIntentService(AdsRecommendationService(repository),repository).list_intents(
            context.seller_id,context.marketplace_id,profile_id,status,limit)
        return {"write_intents":[record.public_dict() for record in records],"count":len(records),
                "message":"Prepared only — no Amazon Ads change has been sent."}
    except ValueError:raise HTTPException(422,"Unsupported write-intent status") from None
    except Exception:raise HTTPException(503,"Write-intent history is unavailable") from None

@router.post("/write-intents/{write_intent_id}/revalidate")
def revalidate_write_intent(write_intent_id:str,payload:WriteIntentRevalidationRequest):
    try:
        context=_context();profile_id=os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:raise HTTPException(503,"Write-intent revalidation is unavailable")
        repository,_,_=_services()
        service=AdsWriteIntentRevalidationService(AdsRecommendationService(repository),repository,
            write_config=AdsWriteConfig.from_environment(),approval_status=os.getenv("AMAZON_ADS_APPROVAL_STATUS","pending"))
        result=service.revalidate(context.seller_id,context.marketplace_id,profile_id,write_intent_id,payload.confirm_revalidation)
        if result.reason_code=="confirmation_required":raise HTTPException(400,"Explicit write-intent revalidation confirmation is required")
        if result.reason_code=="intent_not_found":raise HTTPException(404,"Write intent is not available")
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Write-intent revalidation is unavailable") from None

@router.post("/write-intents/{write_intent_id}/cancel")
def cancel_write_intent(write_intent_id:str,payload:WriteIntentCancelRequest):
    try:
        context=_context();profile_id=os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:raise HTTPException(503,"Write-intent cancellation is unavailable")
        repository,_,_=_services()
        service=AdsWriteIntentRevalidationService(AdsRecommendationService(repository),repository)
        result=service.cancel(context.seller_id,context.marketplace_id,profile_id,write_intent_id,payload.confirm_cancel_write_intent)
        if result.reason_code=="confirmation_required":raise HTTPException(400,"Explicit write-intent cancellation confirmation is required")
        if result.reason_code=="intent_not_found":raise HTTPException(404,"Write intent is not available")
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Write-intent cancellation is unavailable") from None

@router.post("/write-intents/{write_intent_id}/target-resolution")
def resolve_write_target(write_intent_id:str,payload:WriteTargetResolutionRequest):
    try:
        context=_context();profile_id=os.getenv("AMAZON_ADS_PROFILE_ID")
        if not profile_id:raise HTTPException(503,"Advertiser target resolution is unavailable")
        repository,_,_=_services();recommendations=AdsRecommendationService(repository)
        lifecycle=AdsWriteIntentRevalidationService(recommendations,repository,
            write_config=AdsWriteConfig.from_environment(),approval_status=os.getenv("AMAZON_ADS_APPROVAL_STATUS","pending"))
        # No production target resolver or live Amazon provider exists in this step.
        result=AdsWriteTargetResolutionService(repository,lifecycle).resolve(
            context.seller_id,context.marketplace_id,profile_id,write_intent_id,payload.confirm_target_resolution)
        if result.status=="confirmation_required":raise HTTPException(400,"Explicit target-resolution confirmation is required")
        if result.status=="intent_not_found":raise HTTPException(404,"Write intent is not available")
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Advertiser target resolution is unavailable") from None


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

@router.get("/historical-sync-runs")
def historical_sync_runs(limit:int=Query(20,ge=1,le=100)):
    try:
        context=_context();repository,_,_=_services();profile_id=AdsSettings.from_environment().profile_id
        return {"runs":[item.public_dict() for item in repository.list_sync_runs(context.seller_id,context.marketplace_id,profile_id,limit,HISTORICAL_SYNC_MODE)]}
    except Exception:raise HTTPException(503,"Historical Ads sync history is unavailable") from None

@router.get("/historical-sync-health")
def historical_sync_health():
    try:
        context=_context();repository,_,_=_services();return _historical_sync_health_service(repository).get(context.seller_id,context.marketplace_id).public_dict()
    except Exception:raise HTTPException(503,"Historical Ads sync health is unavailable") from None

@router.get("/scheduled-sync-health")
def scheduled_sync_health():
    try:
        context=_context();repository,_,_=_services();return _scheduled_sync_health_service(repository).get(context.seller_id,context.marketplace_id).public_dict()
    except Exception:raise HTTPException(503,"Scheduled Ads sync health is unavailable") from None

@router.post("/manual-historical-sync")
def manual_historical_sync(payload:LiveSmokeTestRequest):
    try:
        context=_context();repository,_,_=_services();result=_manual_historical_sync_service(repository,context).run(context.seller_id,context.marketplace_id,payload.confirm_live_read)
        if result.status=="blocked_confirmation":raise HTTPException(400,"Explicit live-read confirmation is required")
        if result.status=="blocked_readiness":raise HTTPException(422,result.message)
        if result.status=="already_running":raise HTTPException(409,result.message)
        if result.status=="cooldown_active":raise HTTPException(429,result.message)
        if result.status=="unavailable":raise HTTPException(503,result.message)
        return result.public_dict()
    except HTTPException:raise
    except Exception:raise HTTPException(503,"Historical Ads sync is unavailable") from None


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
@router.get("/sync/observability")
def sync_observability(limit:int=Query(20,ge=1,le=100)):
    try:
        context=_context();repository,_,_=_services();settings=AdsSettings.from_environment();gate=AdsSyncGateService(settings,repository,AdsLiveReadConfig.from_environment())
        return AdsSyncObservabilityService(repository,gate).get(context.seller_id,context.marketplace_id,limit=limit).public_dict()
    except Exception:
        raise HTTPException(503,"Ads sync health is unavailable") from None

@router.get("/sync/history")
def sync_history(limit:int=Query(20,ge=1,le=100)):
    try:
        context=_context();repository,_,_=_services();profile_id=AdsSettings.from_environment().profile_id
        return {"runs":[item.public_dict() for item in repository.list_sync_runs(context.seller_id,context.marketplace_id,profile_id,limit)]}
    except Exception:
        raise HTTPException(503,"Ads sync history is unavailable") from None
