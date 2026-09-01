"""Persists offline proposals; approval never activates a rule."""
from app.services.ads_rule_evaluation_service import AdsRuleEvaluationService
class AdsRuleTuningProposalService:
 def __init__(self,repository,effectiveness):self.repository=repository;self.evaluator=AdsRuleEvaluationService(effectiveness)
 def generate(self,seller,marketplace,profile,window=90):
  baseline,proposals,evaluation=self.evaluator.evaluate(seller,marketplace,profile,window)
  for proposal in proposals:self.repository.save_rule_tuning_proposal(proposal)
  return {"baseline":baseline.public_dict(),"proposals":[p.public_dict() for p in proposals],"evaluation":evaluation}