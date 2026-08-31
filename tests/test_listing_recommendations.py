from datetime import datetime,timezone
from app.services.listing_intelligence_service import ListingIntelligence
from app.services.listing_recommendation_service import ListingRecommendationService

def intelligence(flags=(),risk=10,stability=80,count=10,confidence="high"):
    return ListingIntelligence("ASIN","seller","market",None,None,30,count,"10","10","10","10","10","0","0","flat",0,0,0,0,0,0,count,0.0,None,stability,risk,50,confidence,flags,())
def test_no_history_waits_for_data(): assert ListingRecommendationService().recommend(intelligence(("INSUFFICIENT_HISTORY",),count=0,confidence="low")).overall_action == "WAIT_FOR_MORE_DATA"
def test_stable_listing_is_kept_stable(): assert ListingRecommendationService().recommend(intelligence()).overall_action == "KEEP_STABLE"
def test_risk_rule_mapping_and_priority():
    result=ListingRecommendationService().recommend(intelligence(("STATUS_UNSTABLE","PRICE_VOLATILE","TITLE_FREQUENTLY_CHANGED"),80,20))
    assert result.priority == "critical" and {item.action for item in result.recommendations} >= {"CHECK_LISTING_STATUS","REVIEW_PRICE_VOLATILITY","REVIEW_TITLE"}
def test_fulfillment_and_recent_change():
    result=ListingRecommendationService().recommend(intelligence(("FULFILLMENT_UNSTABLE","RECENT_MAJOR_CHANGE"),50,40))
    assert {item.action for item in result.recommendations} == {"REVIEW_FULFILLMENT","INVESTIGATE_RECENT_CHANGE"}
def test_deterministic_and_safe():
    service=ListingRecommendationService(); now=datetime(2026,1,1,tzinfo=timezone.utc); first=service.recommend(intelligence(("PRICE_VOLATILE",),60),now); second=service.recommend(intelligence(("PRICE_VOLATILE",),60),now)
    assert first == second and "token" not in str(first.public_dict()).lower() and "secret" not in str(first.public_dict()).lower()
