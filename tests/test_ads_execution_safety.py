from decimal import Decimal
import pytest
from app.services.ads_execution_safety_service import AdsExecutionSafetyConfig, AdsExecutionSafetyConfigurationError, AdsExecutionSafetyService


def test_execution_safety_defaults_to_dry_run_and_decimal_limit(monkeypatch):
    for name in ("AMAZON_ADS_EXECUTION_ENABLED","AMAZON_ADS_DRY_RUN_ONLY"): monkeypatch.delenv(name, raising=False)
    config = AdsExecutionSafetyConfig.from_environment()
    assert config.execution_enabled is False and config.dry_run_only is True
    service = AdsExecutionSafetyService(config)
    assert service.percentage_within_limit(Decimal("100"), Decimal("120"), Decimal("20")) is True
    assert service.percentage_within_limit(Decimal("100"), Decimal("121"), Decimal("20")) is False


def test_execution_safety_rejects_invalid_configuration(monkeypatch):
    monkeypatch.setenv("AMAZON_ADS_MAX_BID_INCREASE_PERCENT", "invalid")
    with pytest.raises(AdsExecutionSafetyConfigurationError): AdsExecutionSafetyConfig.from_environment()
