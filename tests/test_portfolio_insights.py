from datetime import datetime,timezone,timedelta
from app.amazon.models import Listing
from app.database.repository import ListingSnapshotRepository
from app.services.listing_intelligence_service import ListingIntelligenceService
from app.services.listing_recommendation_service import ListingRecommendationService
from app.services.recommendation_explanation_service import RecommendationExplanationService
from app.services.listing_insights_service import ListingInsightsService
from app.services.portfolio_insights_service import PortfolioInsightsService

def service(tmp_path):
    repo=ListingSnapshotRepository(tmp_path/"portfolio.db"); insights=ListingInsightsService(repo,ListingIntelligenceService(repo),ListingRecommendationService(),RecommendationExplanationService()); return repo,PortfolioInsightsService(repo,insights)
def item(asin,status="ACTIVE",price="10",seller="seller",market="market"): return Listing(seller,market,"SKU",asin,title="Title",price=price,currency="INR",listing_status=status)
def test_empty_portfolio(tmp_path):
    _,value=service(tmp_path); result=value.get_portfolio("seller","market","all",now=datetime.now(timezone.utc)); assert result.total_listings == 0 and result.listings == ()
def test_multiple_sort_filters_and_isolation(tmp_path):
    repo,value=service(tmp_path); now=datetime.now(timezone.utc)
    for offset in (10,5,1): repo.save_listing_snapshot(item("B000000001","ACTIVE","10"),now-timedelta(days=offset))
    repo.save_listing_snapshot(item("B000000002","INACTIVE","30"),now-timedelta(days=1)); repo.save_listing_snapshot(item("B000000003","ACTIVE","5",seller="other"),now)
    risk=value.get_portfolio("seller","market","all","risk_desc",now=now); assert risk.total_listings == 2 and risk.listings[0]["asin"] == "B000000002" and "listing_hash" not in str(risk.public_dict())
    active=value.get_portfolio("seller","market","all","stability_desc",status="ACTIVE",limit=1,now=now); assert active.total_listings == 1 and active.listings[0]["listing_status"] == "ACTIVE"
def test_priority_confidence_and_recent_filters(tmp_path):
    repo,value=service(tmp_path); now=datetime.now(timezone.utc); repo.save_listing_snapshot(item("B000000001","ACTIVE"),now-timedelta(days=1)); repo.save_listing_snapshot(item("B000000002","INACTIVE"),now)
    high=value.get_portfolio("seller","market","all",priority="high",now=now); assert all(record["priority"]=="high" for record in high.listings)
    low=value.get_portfolio("seller","market","all",confidence="low",changed_recently=True,min_risk_score=0,now=now); assert low.total_listings >= 1 and "secret" not in str(low.public_dict()).lower()
