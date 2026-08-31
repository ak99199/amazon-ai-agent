from datetime import datetime,timezone
from app.services.listing_recommendation_service import Recommendation,RecommendationResult
from app.services.recommendation_explanation_service import RecommendationExplanationService

def recommendation(): return RecommendationResult("ASIN","seller","market","2026-01-01T00:00:00+00:00","CHECK_LISTING_STATUS","high",(Recommendation("CHECK_LISTING_STATUS","high","Status changed.",{"risk_flag":"STATUS_UNSTABLE"},"Review manually."),),"Status changed.","medium",70,20,40)
class Provider:
    def __init__(self,value=None,error=False): self.value=value; self.error=error
    def explain(self,payload):
        if self.error: raise RuntimeError("secret-token")
        return self.value
def valid(): return {"headline":"Review status","summary":"Status requires review.","overall_action":"CHECK_LISTING_STATUS","priority":"high","action_explanations":[{"action":"CHECK_LISTING_STATUS","priority":"high","explanation":"Review status manually."}]}
def test_no_provider_falls_back_deterministically():
    now=datetime(2026,1,1,tzinfo=timezone.utc); first=RecommendationExplanationService().explain(recommendation(),now); second=RecommendationExplanationService().explain(recommendation(),now); assert first == second and first.source == "deterministic"
def test_valid_provider_can_explain_without_changing_rules(): assert RecommendationExplanationService(Provider(valid())).explain(recommendation()).source == "llm"
def test_invalid_action_or_priority_falls_back():
    bad=valid(); bad["action_explanations"][0]["action"]="INVENT_ACTION"; assert RecommendationExplanationService(Provider(bad)).explain(recommendation()).source == "deterministic"
    bad=valid(); bad["priority"]="critical"; assert RecommendationExplanationService(Provider(bad)).explain(recommendation()).source == "deterministic"
def test_provider_failure_and_secret_safety():
    result=RecommendationExplanationService(Provider(error=True)).explain(recommendation()); assert result.source == "deterministic" and "secret-token" not in str(result.public_dict())
