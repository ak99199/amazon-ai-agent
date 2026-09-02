from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from app.amazon_ads.value_proposal_models import AdsValueProposalConfig
from app.amazon_ads.write_models import AdsWriteConfig
from app.services.ads_exact_value_proposal_service import AdsExactValueProposalService
from app.services.ads_execution_safety_service import AdsExecutionSafetyConfig, AdsExecutionSafetyService
from app.services.ads_write_preflight_service import AdsWritePreflightService
from tests.test_ads_write_preflight_service import Recommendations, Repo, fixtures, recommendation


NOW = datetime(2026, 2, 11, tzinfo=timezone.utc)


class Provider:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def resolve_current_value(self, *args):
        self.calls.append(args)
        return self.value


def safety(maximum=Decimal("20"), amount=Decimal("10"), actions=1):
    config = AdsExecutionSafetyConfig(max_bid_increase_percent=maximum,
        max_bid_decrease_percent=maximum, max_single_action_amount=amount,
        max_actions_per_run=actions)
    return AdsExecutionSafetyService(config)


def service(percent="10", value="1.00", plan_changes=None, current_marker="default",
            decision_marker="default", provider_marker="default", maximum=Decimal("20"),
            amount=Decimal("10"), actions=1, config_valid=True):
    current, decision, plan = fixtures()
    if plan_changes:
        plan = replace(plan, **plan_changes)
    current = current if current_marker == "default" else current_marker
    if current_marker != "default" and current is not None and plan_changes:
        plan = replace(plan, recommendation_id=current.recommendation_id)
        decision = replace(decision, recommendation_id=current.recommendation_id,
                           recommendation_code=current.recommendation_code)
    decision = decision if decision_marker == "default" else decision_marker
    provider = Provider(value) if provider_marker == "default" else provider_marker
    result = AdsExactValueProposalService(Recommendations(current), Repo(plan, decision),
        provider, AdsValueProposalConfig(Decimal(percent), config_valid),
        safety(maximum, amount, actions), AdsWriteConfig(True, True, True),
        now=lambda: NOW).propose("s", "m", "p", "plan", True)
    return result, provider, current, decision, plan


def test_configuration_defaults_and_malformed_values_fail_closed(monkeypatch):
    monkeypatch.delenv("AMAZON_ADS_BID_PROPOSAL_PERCENT", raising=False)
    assert AdsValueProposalConfig.from_environment().bid_proposal_percent == 0
    result, *_ = service(percent="0")
    assert result.proposal_status == "proposal_percent_not_configured"
    for raw in ("bad", "NaN", "Infinity", "-1"):
        monkeypatch.setenv("AMAZON_ADS_BID_PROPOSAL_PERCENT", raw)
        assert AdsValueProposalConfig.from_environment().valid is False


def test_missing_provider_plan_decision_staleness_and_scope_fail_closed():
    assert service(provider_marker=None)[0].proposal_status == "current_value_unavailable"
    current, decision, _ = fixtures()
    result = AdsExactValueProposalService(Recommendations(current), Repo(None, decision),
        Provider("1"), AdsValueProposalConfig(Decimal("10")), safety(),
        AdsWriteConfig(True, True, True), now=lambda: NOW).propose("s", "m", "p", "plan", True)
    assert result.proposal_status == "plan_not_found"
    assert service(decision_marker=replace(decision, status="rejected"))[0].proposal_status == "decision_not_approved"
    assert service(current_marker=None)[0].proposal_status == "stale_recommendation"
    assert service(plan_changes={"seller_id": "other"})[0].proposal_status == "scope_mismatch"


def test_only_bid_direction_and_exact_direction_are_supported():
    assert service(plan_changes={"action_type": "KEYWORD_RESEARCH_REVIEW"})[0].proposal_status == "exact_value_not_applicable"
    assert service(plan_changes={"direction": "none"})[0].proposal_status == "invalid_direction"


def test_invalid_trusted_current_values_fail_closed():
    for value in (None, "0", "-1", "NaN", "Infinity", "bad"):
        result, *_ = service(value=value)
        assert result.proposal_status == "current_value_unavailable"


def test_decimal_increase_decrease_quantization_and_idempotency():
    increase, provider, *_ = service(percent="10", value="1.05")
    decrease_current = replace(recommendation("BID_DECREASE_CANDIDATE"),
                               suggested_bid_direction="decrease")
    decrease, *_ = service(percent="10", value="1.05",
                           plan_changes={"direction": "decrease",
                                         "recommendation_code": "BID_DECREASE_CANDIDATE"},
                           current_marker=decrease_current)
    repeated, *_ = service(percent="10", value="1.05")
    assert increase.current_value == "1.05" and increase.proposed_value == "1.16"
    assert decrease.proposed_value == "0.95"
    assert increase.eligible and increase.proposal_id == repeated.proposal_id
    assert len(provider.calls) == 1


def test_direction_rounding_percentage_amount_and_action_limits_block():
    assert service(percent="0.01", value="0.01")[0].proposal_status == "direction_inconsistent"
    assert service(percent="21", maximum=Decimal("20"))[0].proposal_status == "hard_limit_violation"
    assert service(percent="10", value="10", amount=Decimal("10"))[0].proposal_status == "hard_limit_violation"
    assert service(actions=0)[0].proposal_status == "hard_limit_violation"


def test_preflight_accepts_only_matching_trusted_proposal_and_still_has_no_transport():
    proposal, _, current, decision, plan = service()
    preflight = AdsWritePreflightService(Recommendations(current), Repo(plan, decision),
        AdsWriteConfig(True, True, True), "approved", safety_service=safety(), now=lambda: NOW)
    assert preflight.preflight("s", "m", "p", "plan", True).status == "exact_value_required"
    accepted = preflight.preflight("s", "m", "p", "plan", True, proposal=proposal)
    assert accepted.status == "eligible_preflight" and accepted.eligible
    assert not hasattr(AdsExactValueProposalService, "execute")
    assert not hasattr(AdsExactValueProposalService, "apply")
    assert not hasattr(AdsExactValueProposalService, "push")
    public = proposal.public_dict()
    assert all(term not in str(public).lower() for term in
               ("access_token", "refresh_token", "client_secret", "authorization", "signed_url"))
