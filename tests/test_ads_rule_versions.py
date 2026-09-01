from app.amazon_ads.rule_versions import AdsRuleVersions
def test_baseline_rule_version_is_safe_and_active_only_as_baseline():
 a=AdsRuleVersions.baseline("s","m","p");b=AdsRuleVersions.baseline("other","m","p")
 assert a.status=="active" and a.seller_id!=b.seller_id and "client_secret" not in a.public_dict()