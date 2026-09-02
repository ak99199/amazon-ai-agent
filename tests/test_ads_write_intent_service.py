from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.amazon_ads.write_intent_models import AdsWriteIntentBlockedError
from app.amazon_ads.write_models import AdsWriteConfig
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_write_intent_service import AdsWriteIntentService
from app.services.ads_write_preflight_service import AdsWritePreflightService
from tests.test_ads_exact_value_proposal_service import service as proposal_service, safety
from tests.test_ads_write_preflight_service import Recommendations, Repo


NOW = datetime(2026, 2, 12, tzinfo=timezone.utc)


class IntentRepo(Repo):
    def __init__(self, plan, decision):
        super().__init__(plan, decision)
        self.intents = {}

    def save_write_intent(self, intent):
        return self.intents.setdefault(intent.idempotency_key, intent)

    def list_write_intents(self, seller, marketplace, profile, status=None, limit=50):
        rows = [row for row in self.intents.values() if row.seller_id == seller and
                row.marketplace_id == marketplace and row.profile_id == str(profile) and
                (status is None or row.status == status)]
        return rows[:limit]


def trusted():
    proposal, _, current, decision, plan = proposal_service()
    preflight = AdsWritePreflightService(Recommendations(current), Repo(plan, decision),
        AdsWriteConfig(True, True, True), "approved", safety_service=safety(),
        now=lambda: NOW).preflight("s", "m", "p", "plan", True, proposal=proposal)
    repository = IntentRepo(plan, decision)
    service = AdsWriteIntentService(Recommendations(current), repository,
        AdsWriteConfig(True, True, True), "approved", safety(), now=lambda: NOW)
    return service, repository, current, decision, plan, proposal, preflight


def blocked(service, status, **changes):
    with pytest.raises(AdsWriteIntentBlockedError) as captured:
        service.prepare("s", "m", "p", "plan", **changes)
    assert captured.value.status == status


def test_confirmation_plan_decision_eligibility_and_dry_run_gates():
    service, repo, _, decision, plan, proposal, preflight = trusted()
    blocked(service, "confirmation_required", proposal=proposal, preflight=preflight)
    repo.plan = None
    blocked(service, "plan_not_found", confirm=True, proposal=proposal, preflight=preflight)
    repo.plan = plan; repo.decision = replace(decision, status="rejected")
    blocked(service, "decision_not_approved", confirm=True, proposal=proposal, preflight=preflight)
    repo.decision = decision; repo.plan = replace(plan, eligible=False)
    blocked(service, "plan_not_eligible", confirm=True, proposal=proposal, preflight=preflight)
    repo.plan = replace(plan, dry_run=False)
    blocked(service, "plan_not_dry_run", confirm=True, proposal=proposal, preflight=preflight)


def test_stale_scope_proposal_and_preflight_mismatches_block():
    service, repo, _, _, plan, proposal, preflight = trusted()
    service.recommendations.current = None
    blocked(service, "stale_recommendation", confirm=True, proposal=proposal, preflight=preflight)
    for field in ("seller_id", "marketplace_id", "profile_id"):
        service, repo, current, _, plan, proposal, preflight = trusted()
        repo.plan = replace(plan, **{field: "other"})
        blocked(service, "scope_mismatch", confirm=True, proposal=proposal, preflight=preflight)
    service, *_ = trusted()
    blocked(service, "proposal_required", confirm=True, preflight=preflight)
    blocked(service, "proposal_not_eligible", confirm=True,
            proposal=replace(proposal, eligible=False), preflight=preflight)
    blocked(service, "proposal_plan_mismatch", confirm=True,
            proposal=replace(proposal, execution_plan_id="other"), preflight=preflight)
    blocked(service, "proposal_decision_mismatch", confirm=True,
            proposal=replace(proposal, decision_id="other"), preflight=preflight)
    blocked(service, "preflight_required", confirm=True, proposal=proposal)
    blocked(service, "preflight_not_eligible", confirm=True, proposal=proposal,
            preflight=replace(preflight, eligible=False))
    blocked(service, "preflight_plan_mismatch", confirm=True, proposal=proposal,
            preflight=replace(preflight, execution_plan_id="other"))


def test_exact_values_direction_action_and_hard_limits_are_revalidated():
    service, repo, current, _, plan, proposal, preflight = trusted()
    blocked(service, "current_value_mismatch", confirm=True, proposal=proposal,
            preflight=replace(preflight, current_value="9.99"))
    blocked(service, "proposed_value_mismatch", confirm=True, proposal=proposal,
            preflight=replace(preflight, proposed_value="9.99"))
    repo.plan = replace(plan, action_type="KEYWORD_RESEARCH_REVIEW")
    altered = replace(proposal, action_type="KEYWORD_RESEARCH_REVIEW")
    altered_preflight = replace(preflight, action_type="KEYWORD_RESEARCH_REVIEW")
    blocked(service, "unsupported_action", confirm=True, proposal=altered, preflight=altered_preflight)
    service, repo, _, _, plan, proposal, preflight = trusted()
    repo.plan = replace(plan, direction="decrease")
    altered = replace(proposal, direction="decrease")
    altered_preflight = replace(preflight, direction="decrease")
    blocked(service, "invalid_direction", confirm=True, proposal=altered, preflight=altered_preflight)
    service, repo, *_rest, proposal, preflight = trusted()
    service.safety = safety(amount=0)
    blocked(service, "hard_limit_violation", confirm=True, proposal=proposal, preflight=preflight)


def test_preparation_is_deterministic_and_public_output_is_safe():
    service, repo, _, _, _, proposal, preflight = trusted()
    first = service.prepare("s", "m", "p", "plan", True, proposal, preflight)
    second = service.prepare("s", "m", "p", "plan", True, proposal, preflight)
    assert first.write_intent_id == second.write_intent_id
    assert first.idempotency_key == second.idempotency_key and len(repo.intents) == 1
    public = first.public_dict()
    assert public["status"] == "prepared"
    assert all(term not in str(public).lower() for term in
               ("access_token", "refresh_token", "client_secret", "authorization", "raw_request"))
    assert not hasattr(AdsWriteIntentService, "execute")
    assert not hasattr(AdsWriteIntentService, "apply")
    assert not hasattr(AdsWriteIntentService, "push")


def test_sqlite_idempotency_audit_and_scope_isolation(tmp_path):
    service, _, _, _, _, proposal, preflight = trusted()
    intent = service.prepare("s", "m", "p", "plan", True, proposal, preflight)
    repository = AdsPerformanceRepository(tmp_path / "ads.db")
    first = repository.save_write_intent(intent)
    second = repository.save_write_intent(intent)
    assert first.write_intent_id == second.write_intent_id
    assert len(repository.list_write_intents("s", "m", "p")) == 1
    assert repository.list_write_intents("other", "m", "p") == []
    assert repository.list_write_intents("s", "other", "p") == []
    assert repository.list_write_intents("s", "m", "other") == []
    events = repository.list_write_intent_events("s", "m", "p", intent.write_intent_id)
    assert len(events) == 1 and events[0]["event_type"] == "WRITE_INTENT_PREPARED"
