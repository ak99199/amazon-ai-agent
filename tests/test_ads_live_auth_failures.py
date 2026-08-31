from app.amazon_ads.client import AmazonAdsClient

def test_live_error_classification_is_sanitized_and_retryable_only_when_safe():
 assert AmazonAdsClient._normalize_error(401).public_error().message=="Amazon Ads authorization is invalid or expired"
 assert AmazonAdsClient._normalize_error(403).retryable is False
 assert AmazonAdsClient._normalize_error(429).retryable is True
 assert "token" not in str(AmazonAdsClient._normalize_error(401)).lower()
