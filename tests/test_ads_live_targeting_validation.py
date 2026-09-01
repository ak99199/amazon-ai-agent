from datetime import datetime, timezone

import pytest

from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.models import AdsProfile
from app.services.ads_live_targeting_validation_service import AdsLiveTargetingValidationService
from app.services.ads_production_readiness_service import AdsProductionReadinessService


NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)


def readiness(approval="approved", settings=None, config=None):
    return AdsProductionReadinessService(
        settings or AdsSettings("id", "secret", "refresh", "configured-profile", "FE"),
        config or AdsLiveReadConfig(True, False),
        approval,
    )


class Profiles:
    def __init__(self, error=None):
        self.error = error

    def list_profiles(self):
        if self.error:
            raise self.error
        return [AdsProfile("configured-profile", "IN", "INR")]


class Adapter:
    def __init__(self, campaigns=None, ad_groups=None, keywords=None, targets=None, error=None):
        self.rows = [campaigns or [], ad_groups or [], keywords or [], targets or []]
        self.error = error
        self.calls = []

    def _read(self, name, profile, maximum):
        self.calls.append((name, profile, maximum))
        if self.error:
            raise self.error
        return self.rows[len(self.calls) - 1]

    def first_campaign_page(self, profile, maximum):
        return self._read("campaigns", profile, maximum)

    def first_ad_group_page(self, profile, maximum):
        return self._read("ad_groups", profile, maximum)

    def first_keyword_page(self, profile, maximum):
        return self._read("keywords", profile, maximum)

    def first_target_page(self, profile, maximum):
        return self._read("targets", profile, maximum)

    @staticmethod
    def _ad_group(row):
        from app.amazon_ads.read_adapters import SponsoredProductsReadAdapter
        return SponsoredProductsReadAdapter._ad_group(row)

    @staticmethod
    def _target(row):
        from app.amazon_ads.read_adapters import SponsoredProductsReadAdapter
        return SponsoredProductsReadAdapter._target(row)


def run(adapter=None, ready=None, profiles=None):
    adapter = adapter or Adapter()
    service = AdsLiveTargetingValidationService(
        ready or readiness(), lambda: (profiles or Profiles(), adapter), now=lambda: NOW
    )
    return service.run(True), adapter


@pytest.mark.parametrize(
    "ready",
    [
        readiness("pending"),
        readiness("rejected"),
        readiness(settings=AdsSettings(None, "secret", "refresh", "configured-profile", "FE")),
        readiness(settings=AdsSettings("id", "secret", "refresh", None, "FE")),
        readiness(config=AdsLiveReadConfig(False, False)),
        readiness(config=AdsLiveReadConfig(True, True)),
        readiness(settings=AdsSettings("id", "secret", "refresh", "configured-profile", "XX")),
    ],
)
def test_unsafe_readiness_makes_zero_dependency_calls(ready):
    calls = []
    result = AdsLiveTargetingValidationService(ready, lambda: calls.append(True), now=lambda: NOW).run(True)
    assert result.status == "blocked_readiness"
    assert calls == []


def test_confirmation_false_makes_zero_dependency_calls():
    calls = []
    result = AdsLiveTargetingValidationService(readiness(), lambda: calls.append(True), now=lambda: NOW).run(False)
    assert result.status == "blocked_confirmation"
    assert calls == []


def test_configured_profile_is_never_auto_selected_when_missing():
    class OtherProfiles:
        def list_profiles(self):
            return [AdsProfile("other-profile", "IN", "INR")]

    result, adapter = run(profiles=OtherProfiles())
    assert result.status == "profile_not_found"
    assert result.profile_summary["matched"] is False
    assert adapter.calls == []


def test_real_adapter_uses_one_get_per_entity_and_clamps_returned_rows():
    from app.amazon_ads.read_adapters import SponsoredProductsReadAdapter

    class Client:
        def __init__(self):
            self.calls = []

        def get_profile_scoped(self, path, params, profile_id):
            self.calls.append((path, params, profile_id))
            key = {"/sp/campaigns": "campaigns", "/sp/adGroups": "adGroups", "/sp/keywords": "keywords", "/sp/targets": "targets"}[path]
            return {key: list(range(100)), "nextToken": "must-not-be-followed"}

    client = Client()
    adapter = SponsoredProductsReadAdapter(client, max_pages=100, page_size=100)
    assert len(adapter.first_campaign_page("p", 99)) == 10
    assert len(adapter.first_ad_group_page("p", 99)) == 20
    assert len(adapter.first_keyword_page("p", 99)) == 25
    assert len(adapter.first_target_page("p", 99)) == 25
    assert [call[1]["maxResults"] for call in client.calls] == [10, 20, 25, 25]
    assert len(client.calls) == 4


def test_valid_entities_are_read_once_in_order_with_fixed_bounds():
    adapter = Adapter(
        campaigns=[{"campaignId": "c1", "state": "enabled"}],
        ad_groups=[{"adGroupId": "g1", "campaignId": "c1", "state": "enabled", "defaultBid": "1"}],
        keywords=[{"keywordId": "k1", "campaignId": "c1", "adGroupId": "g1", "keywordText": "safe", "matchType": "exact", "state": "enabled", "bid": "1"}],
        targets=[{"targetId": "t1", "campaignId": "c1", "adGroupId": "g1", "expression": [{"type": "asinSameAs", "value": "B000"}], "state": "enabled", "bid": "1"}],
    )
    result, _ = run(adapter)
    assert result.status == "success"
    assert adapter.calls == [("campaigns", "configured-profile", 10), ("ad_groups", "configured-profile", 20), ("keywords", "configured-profile", 25), ("targets", "configured-profile", 25)]
    assert result.relationships == {"valid": 3, "invalid": 0, "unresolved": 0, "bounded": True}
    assert all(getattr(result, name)["records_valid"] == 1 for name in ("campaigns", "ad_groups", "keywords", "targets"))


def test_normalized_snake_case_fields_share_the_canonical_validation_boundary():
    adapter = Adapter(
        campaigns=[{"campaign_id": "c1", "state": "enabled"}],
        ad_groups=[{"ad_group_id": "g1", "campaign_id": "c1", "default_bid": "1"}],
        keywords=[{"keyword_id": "k1", "campaign_id": "c1", "ad_group_id": "g1", "keyword_text": "safe", "match_type": "exact", "bid": "1"}],
        targets=[{"target_id": "t1", "campaign_id": "c1", "ad_group_id": "g1", "expression": "safe", "bid": "1"}],
    )
    result, _ = run(adapter)
    assert result.status == "success"
    assert result.relationships == {"valid": 3, "invalid": 0, "unresolved": 0, "bounded": True}


def test_malformed_duplicate_invalid_bid_match_state_and_expression_are_isolated():
    adapter = Adapter(
        campaigns=[{"campaignId": "c1", "state": "enabled"}],
        ad_groups=[{"adGroupId": "g1", "campaignId": "c1", "defaultBid": "1"}, {"adGroupId": "g1", "campaignId": "c1"}, {"bad": True}, {"adGroupId": "g2", "campaignId": "c1", "defaultBid": "NaN"}],
        keywords=[{"keywordId": "k1", "adGroupId": "g1", "matchType": "exact", "bid": "1"}, {"keywordId": "k1", "adGroupId": "g1"}, {"keywordId": "k2", "adGroupId": "g1", "matchType": "invented"}, {"keywordId": "k3", "adGroupId": "g1", "bid": "-1"}, {}],
        targets=[{"targetId": "t1", "adGroupId": "g1", "expression": ["safe"]}, {"targetId": "t1", "adGroupId": "g1"}, {"targetId": "t2", "adGroupId": "g1", "expression": []}, {"targetId": "t3", "adGroupId": "g1", "bid": "Infinity"}, {}],
    )
    result, _ = run(adapter)
    assert result.status == "partial_valid"
    assert result.ad_groups == {"records_received": 4, "records_valid": 1, "records_invalid": 2, "duplicate_count": 1, "bounded": True}
    assert result.keywords == {"records_received": 5, "records_valid": 1, "records_invalid": 3, "duplicate_count": 1, "bounded": True}
    assert result.targets == {"records_received": 5, "records_valid": 1, "records_invalid": 3, "duplicate_count": 1, "bounded": True}


@pytest.mark.parametrize("keywords,targets", [([], []), ([{"keywordId": "k", "adGroupId": "g", "matchType": "broad"}], []), ([], [{"targetId": "t", "adGroupId": "g", "expression": "safe"}])])
def test_empty_and_mixed_keyword_target_types_are_valid(keywords, targets):
    adapter = Adapter(campaigns=[{"campaignId": "c"}], ad_groups=[{"adGroupId": "g", "campaignId": "c"}], keywords=keywords, targets=targets)
    result, _ = run(adapter)
    assert result.status == "success"


def test_missing_bounded_parent_is_unresolved_but_proven_campaign_mismatch_is_invalid():
    adapter = Adapter(
        campaigns=[{"campaignId": "c1"}],
        ad_groups=[{"adGroupId": "g1", "campaignId": "outside"}],
        keywords=[{"keywordId": "k1", "campaignId": "different", "adGroupId": "g1", "matchType": "exact"}, {"keywordId": "k2", "adGroupId": "outside-group", "matchType": "phrase"}],
        targets=[{"targetId": "t1", "adGroupId": "outside-group", "expression": "safe"}],
    )
    result, _ = run(adapter)
    assert result.relationships == {"valid": 0, "invalid": 1, "unresolved": 3, "bounded": True}


@pytest.mark.parametrize("status,expected", [(401, "auth_error"), (403, "auth_error"), (429, "rate_limited"), (500, "remote_error")])
def test_remote_errors_are_safely_classified(status, expected):
    result, _ = run(Adapter(error=AdsApiClientError(status, "raw access_token Authorization secret")))
    assert result.status == expected
    assert not any(value in str(result.public_dict()) for value in ("access_token", "Authorization", "raw"))


def test_timeout_is_remote_error_and_malformed_response_is_validation_error():
    timeout, _ = run(Adapter(error=TimeoutError("raw refresh token")))
    malformed = Adapter()
    malformed.rows[2] = None
    invalid, _ = run(malformed)
    assert timeout.status == "remote_error"
    assert invalid.status == "validation_error"
