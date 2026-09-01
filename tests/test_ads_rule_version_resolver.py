from decimal import Decimal
import json
import pytest
from app.database.ads_repository import AdsPerformanceRepository
from app.database.connection import get_connection
from app.services.ads_rule_version_resolver import AdsRuleVersionConfigurationError,AdsRuleVersionResolver
from app.services.ads_signal_service import AdsRecommendationThresholds

FULL={"target_acos_percent":"25","min_impressions_for_ctr":"120","low_ctr_percent":"0.4","min_clicks_for_cvr":"12","low_cvr_percent":"3","high_cpc_amount":"40","wasted_spend_threshold":"400"}

def version(repo,version_id="active",status="active",thresholds=None,**scope):
 return repo.create_rule_version(version_id,scope.get("seller","seller"),scope.get("market","market"),scope.get("profile","profile"),"Safe version",status,thresholds or FULL,"manual","tester")

def test_no_active_uses_exact_environment_defaults_without_writing(tmp_path,monkeypatch):
 monkeypatch.setenv("AMAZON_ADS_TARGET_ACOS_PERCENT","27.5");monkeypatch.setenv("AMAZON_ADS_MIN_CLICKS_FOR_CVR","14")
 repo=AdsPerformanceRepository(tmp_path/"ads.db");resolved=AdsRuleVersionResolver(repo).resolve("seller","market","profile")
 assert resolved.fallback_used and not resolved.is_persisted and resolved.rule_version_id is None
 assert resolved.thresholds==AdsRecommendationThresholds.from_environment()
 assert resolved.thresholds.target_acos_percent==Decimal("27.5") and resolved.thresholds.min_clicks_for_cvr==14
 assert repo.list_rule_versions("seller","market","profile")==[]

def test_active_snapshot_and_metadata_are_resolved(tmp_path):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");version(repo)
 resolved=AdsRuleVersionResolver(repo).resolve("seller","market","profile")
 assert not resolved.fallback_used and resolved.is_persisted and resolved.rule_version_id=="active" and resolved.rule_version_name=="Safe version" and resolved.source=="manual"
 assert resolved.thresholds.target_acos_percent==Decimal("25") and resolved.thresholds.min_impressions_for_ctr==120

@pytest.mark.parametrize("field,value",[("seller","other"),("market","other"),("profile","other")])
def test_scope_isolation_falls_back_for_other_scope(tmp_path,field,value):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");version(repo)
 scope={"seller":"seller","market":"market","profile":"profile",field:value};resolved=AdsRuleVersionResolver(repo).resolve(scope["seller"],scope["market"],scope["profile"])
 assert resolved.fallback_used and resolved.rule_version_id is None

@pytest.mark.parametrize("status",["proposed","archived","rejected"])
def test_non_active_versions_are_ignored(tmp_path,status):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");version(repo,status=status)
 assert AdsRuleVersionResolver(repo).resolve("seller","market","profile").fallback_used

@pytest.mark.parametrize("payload",['{bad',json.dumps({"unknown":"1"}),json.dumps(dict(FULL,target_acos_percent="bad")),json.dumps(dict(FULL,target_acos_percent="101")),json.dumps({"target_acos_percent":"25"})])
def test_corrupt_active_snapshot_never_silently_falls_back(tmp_path,payload):
 repo=AdsPerformanceRepository(tmp_path/"ads.db");version(repo)
 with get_connection(repo._database_path) as connection:connection.execute("UPDATE ads_rule_versions SET thresholds_json=? WHERE rule_version_id='active'",(payload,))
 with pytest.raises(AdsRuleVersionConfigurationError):AdsRuleVersionResolver(repo).resolve("seller","market","profile")

def test_repository_failure_becomes_controlled_configuration_error():
 class Broken:
  def get_active_rule_version(self,*args):raise RuntimeError("raw database details")
 with pytest.raises(AdsRuleVersionConfigurationError,match="unavailable"):AdsRuleVersionResolver(Broken()).resolve("seller","market","profile")
