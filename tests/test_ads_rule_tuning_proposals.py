from decimal import Decimal
from app.amazon_ads.rule_tuning_models import AdsRuleTuningProposal
def test_proposal_identity_is_deterministic():
 assert AdsRuleTuningProposal.identity("s","m","p","b","target_acos_percent",Decimal("30"),Decimal("33"),90)==AdsRuleTuningProposal.identity("s","m","p","b","target_acos_percent",Decimal("30"),Decimal("33"),90)