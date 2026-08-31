"""Centralized deterministic checks for dry-run-only Ads planning."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from os import getenv


class AdsExecutionSafetyConfigurationError(ValueError): pass


@dataclass(frozen=True)
class AdsExecutionSafetyConfig:
    execution_enabled: bool = False
    dry_run_only: bool = True
    max_bid_increase_percent: Decimal = Decimal("20")
    max_bid_decrease_percent: Decimal = Decimal("20")
    max_budget_increase_percent: Decimal = Decimal("20")
    max_budget_decrease_percent: Decimal = Decimal("20")
    max_single_action_amount: Decimal = Decimal("0")
    max_actions_per_run: int = 1

    @classmethod
    def from_environment(cls):
        def boolean(name, default):
            value=getenv(name)
            if value in (None,""): return default
            if value.lower() not in ("true","false"): raise AdsExecutionSafetyConfigurationError(f"{name} must be true or false")
            return value.lower()=="true"
        def decimal(name, default):
            value=getenv(name)
            if value in (None,""): return default
            try: parsed=Decimal(value)
            except InvalidOperation as error: raise AdsExecutionSafetyConfigurationError(f"{name} must be decimal") from error
            if parsed < 0: raise AdsExecutionSafetyConfigurationError(f"{name} cannot be negative")
            return parsed
        def integer(name, default):
            value=getenv(name)
            if value in (None,""): return default
            try: parsed=int(value)
            except ValueError as error: raise AdsExecutionSafetyConfigurationError(f"{name} must be integer") from error
            if parsed < 1: raise AdsExecutionSafetyConfigurationError(f"{name} must be positive")
            return parsed
        return cls(boolean("AMAZON_ADS_EXECUTION_ENABLED",False),boolean("AMAZON_ADS_DRY_RUN_ONLY",True),decimal("AMAZON_ADS_MAX_BID_INCREASE_PERCENT",Decimal("20")),decimal("AMAZON_ADS_MAX_BID_DECREASE_PERCENT",Decimal("20")),decimal("AMAZON_ADS_MAX_BUDGET_INCREASE_PERCENT",Decimal("20")),decimal("AMAZON_ADS_MAX_BUDGET_DECREASE_PERCENT",Decimal("20")),decimal("AMAZON_ADS_MAX_SINGLE_ACTION_AMOUNT",Decimal("0")),integer("AMAZON_ADS_MAX_ACTIONS_PER_RUN",1))


class AdsExecutionSafetyService:
    def __init__(self, config=None): self.config=config or AdsExecutionSafetyConfig.from_environment()
    @staticmethod
    def check(name, passed, reason): return {"name":name,"passed":bool(passed),"reason":reason}
    def percentage_within_limit(self, current, proposed, maximum_percent):
        current, proposed, maximum_percent=Decimal(str(current)),Decimal(str(proposed)),Decimal(str(maximum_percent))
        if current <= 0:return False
        return abs((proposed-current)/current*Decimal("100")) <= maximum_percent
    def configuration_check(self):
        return self.check("CONFIG_SAFE",self.config.dry_run_only,"Dry-run only is enforced." if self.config.dry_run_only else "Live execution is not implemented; dry-run-only configuration is required.")
