from datetime import datetime,timezone,timedelta
from app.amazon.models import Listing
from app.database.repository import ListingSnapshotRepository
from app.services.listing_intelligence_service import ListingIntelligenceService
from app.services.listing_recommendation_service import ListingRecommendationService
from app.services.recommendation_explanation_service import RecommendationExplanationService
from app.services.listing_insights_service import ListingInsightsService

def service(tmp_path):
    repo=ListingSnapshotRepository(tmp_path/"insights.db")
    return repo,ListingInsightsService(repo,ListingIntelligenceService(repo),ListingRecommendationService(),RecommendationExplanationService())
def item(price="10",title="Title",status="ACTIVE"): return Listing("seller","market","SKU","B012345678",title=title,price=price,currency="INR",listing_status=status)
def test_no_history_is_safe(tmp_path):
    _,value=service(tmp_path); result=value.get_insights("seller","market","B012345678","all",datetime.now(timezone.utc)); assert result.current_listing is None and result.history_summary["snapshot_count"] == 0 and "listing_hash" not in str(result.public_dict())
def test_snapshot_and_passthrough(tmp_path):
    repo,value=service(tmp_path); now=datetime.now(timezone.utc)
    for offset in (10,7,4,1): repo.save_listing_snapshot(item(),now-timedelta(days=offset))
    result=value.get_insights("seller","market","B012345678","all",now)
    assert result.current_listing["sku"] == "SKU" and result.recommendations["overall_action"] == "KEEP_STABLE" and result.explanation["source"] == "deterministic"
def test_risky_and_windowed_history(tmp_path):
    repo,value=service(tmp_path); now=datetime.now(timezone.utc); repo.save_listing_snapshot(item("10","Old","ACTIVE"),now-timedelta(days=40)); repo.save_listing_snapshot(item("30","New","INACTIVE"),now-timedelta(days=2)); result=value.get_insights("seller","market","B012345678","7",now); assert result.history_summary["snapshot_count"] == 1 and result.intelligence["risk_score"] >= 0 and "secret" not in str(result.public_dict()).lower()
def test_incomplete_listing_price_is_safe(tmp_path):
    repo,value=service(tmp_path); now=datetime.now(timezone.utc); repo.save_listing_snapshot(Listing("seller","market","SKU","B012345678"),now); result=value.get_insights("seller","market","B012345678","all",now); assert result.history_summary["price_average"] is None
