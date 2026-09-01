from datetime import datetime, timedelta, timezone
import inspect
import sqlite3

import pytest

from app.database.ads_repository import AdsPerformanceRepository
from app.database.connection import get_connection


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def repository(tmp_path):
    return AdsPerformanceRepository(tmp_path / "ads.db")


def create_version(repository, version_id="v1", status="proposed", seller="seller", marketplace="market", profile="profile", created_at=NOW):
    return repository.create_rule_version(
        version_id,
        seller,
        marketplace,
        profile,
        f"Version {version_id}",
        status,
        {"target_acos_percent": "30"},
        "manual",
        "tester",
        created_at=created_at,
    )


def test_create_and_retrieve_proposed_version_in_same_scope(repository):
    created = create_version(repository)
    retrieved = repository.get_rule_version("seller", "market", "profile", "v1")
    assert created["status"] == "proposed"
    assert retrieved["rule_version_id"] == "v1"
    assert retrieved["thresholds"] == {"target_acos_percent": "30"}


@pytest.mark.parametrize(
    "seller,marketplace,profile",
    [("other", "market", "profile"), ("seller", "other", "profile"), ("seller", "market", "other")],
)
def test_rule_version_scope_isolation(repository, seller, marketplace, profile):
    create_version(repository)
    assert repository.get_rule_version(seller, marketplace, profile, "v1") is None


def test_list_versions_is_scoped_and_newest_first(repository):
    create_version(repository, "v1", created_at=NOW)
    create_version(repository, "v2", created_at=NOW + timedelta(seconds=1))
    create_version(repository, "foreign", seller="other")
    assert [row["rule_version_id"] for row in repository.list_rule_versions("seller", "market", "profile")] == ["v2", "v1"]


def test_active_lookup_and_one_active_constraint(repository):
    create_version(repository, "active-1", "active")
    assert repository.get_active_rule_version("seller", "market", "profile")["rule_version_id"] == "active-1"
    with pytest.raises(sqlite3.IntegrityError):
        create_version(repository, "active-2", "active")


def test_proposed_versions_may_coexist(repository):
    create_version(repository, "v1")
    create_version(repository, "v2")
    assert len(repository.list_rule_versions("seller", "market", "profile")) == 2


def test_threshold_snapshot_is_not_mutable_through_repository_api(repository):
    created = create_version(repository)
    created["thresholds"]["target_acos_percent"] = "99"
    assert repository.get_rule_version("seller", "market", "profile", "v1")["thresholds"]["target_acos_percent"] == "30"
    assert "thresholds" not in inspect.signature(repository.update_rule_version_status).parameters


def test_status_update_is_scoped_and_preserves_thresholds(repository):
    create_version(repository)
    assert repository.update_rule_version_status("other", "market", "profile", "v1", "rejected") is None
    updated = repository.update_rule_version_status("seller", "market", "profile", "v1", "rejected", NOW + timedelta(seconds=1))
    assert updated["status"] == "rejected"
    assert updated["thresholds"] == {"target_acos_percent": "30"}


def test_activation_event_persistence_scope_and_newest_first(repository):
    repository.insert_rule_activation_event("e1", "seller", "market", "profile", "RULE_VERSION_ACTIVATED", None, "v1", NOW, "proposal-1")
    repository.insert_rule_activation_event("e2", "seller", "market", "profile", "RULE_VERSION_ROLLED_BACK", "v2", "v1", NOW + timedelta(seconds=1))
    repository.insert_rule_activation_event("foreign", "other", "market", "profile", "RULE_VERSION_ACTIVATED", None, "x", NOW + timedelta(seconds=2))
    rows = repository.list_rule_activation_events("seller", "market", "profile")
    assert [row["event_id"] for row in rows] == ["e2", "e1"]
    assert rows[1]["source_proposal_id"] == "proposal-1"
    assert repository.get_latest_rule_activation_event("seller", "market", "profile")["event_id"] == "e2"
    assert repository.get_latest_rule_activation_event("seller", "other", "profile") is None
    assert repository.get_latest_rule_activation_event("seller", "market", "other") is None


def test_schema_and_indexes_are_idempotent(repository):
    repository.initialize()
    repository.initialize()
    with get_connection(repository._database_path) as connection:
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(ads_rule_versions)")}
        event_columns = {row[1] for row in connection.execute("PRAGMA table_info(ads_rule_activation_events)")}
    assert "idx_ads_rule_one_active" in indexes
    assert "idx_ads_rule_versions_scope_created" in indexes
    assert "source_proposal_id" in event_columns
