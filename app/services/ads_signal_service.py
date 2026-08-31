"""Deterministic Ads signals and centralized, Decimal-safe thresholds."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from os import getenv


class AdsRecommendationConfigurationError(ValueError):
    """Raised when an explicitly configured recommendation threshold is invalid."""


@dataclass(frozen=True)
class AdsRecommendationThresholds:
    target_acos_percent: Decimal = Decimal("30")
    min_impressions_for_ctr: int = 100
    low_ctr_percent: Decimal = Decimal("0.30")
    min_clicks_for_cvr: int = 10
    low_cvr_percent: Decimal = Decimal("2")
    high_cpc_amount: Decimal = Decimal("50")
    wasted_spend_threshold: Decimal = Decimal("500")

    @classmethod
    def from_environment(cls) -> "AdsRecommendationThresholds":
        def decimal(name: str, default: Decimal) -> Decimal:
            value = getenv(name)
            if value in (None, ""):
                return default
            try:
                parsed = Decimal(value)
            except InvalidOperation as error:
                raise AdsRecommendationConfigurationError(f"{name} must be a decimal number") from error
            if parsed < 0:
                raise AdsRecommendationConfigurationError(f"{name} cannot be negative")
            return parsed

        def integer(name: str, default: int) -> int:
            value = getenv(name)
            if value in (None, ""):
                return default
            try:
                parsed = int(value)
            except ValueError as error:
                raise AdsRecommendationConfigurationError(f"{name} must be an integer") from error
            if parsed < 0:
                raise AdsRecommendationConfigurationError(f"{name} cannot be negative")
            return parsed

        return cls(
            target_acos_percent=decimal("AMAZON_ADS_TARGET_ACOS_PERCENT", Decimal("30")),
            min_impressions_for_ctr=integer("AMAZON_ADS_MIN_IMPRESSIONS_FOR_CTR", 100),
            low_ctr_percent=decimal("AMAZON_ADS_LOW_CTR_PERCENT", Decimal("0.30")),
            min_clicks_for_cvr=integer("AMAZON_ADS_MIN_CLICKS_FOR_CVR", 10),
            low_cvr_percent=decimal("AMAZON_ADS_LOW_CVR_PERCENT", Decimal("2")),
            high_cpc_amount=decimal("AMAZON_ADS_HIGH_CPC_AMOUNT", Decimal("50")),
            wasted_spend_threshold=decimal("AMAZON_ADS_WASTED_SPEND_THRESHOLD", Decimal("500")),
        )


class AdsSignalService:
    """Evaluates normalized aggregate metrics; it makes no network or write calls."""

    def __init__(self, thresholds: AdsRecommendationThresholds | None = None):
        self.thresholds = thresholds or AdsRecommendationThresholds.from_environment()

    def confidence(self, metrics: dict[str, object], days_of_history: int) -> str:
        clicks, spend = int(metrics["clicks"]), Decimal(str(metrics["spend"]))
        if days_of_history >= 14 and (clicks >= 30 or spend >= self.thresholds.wasted_spend_threshold):
            return "high"
        if days_of_history >= 7 and (clicks >= self.thresholds.min_clicks_for_cvr or spend >= self.thresholds.wasted_spend_threshold):
            return "medium"
        return "low"

    def codes(self, metrics: dict[str, object], days_of_history: int, scope_type: str) -> tuple[str, ...]:
        confidence = self.confidence(metrics, days_of_history)
        if confidence == "low":
            return ("INSUFFICIENT_DATA",)
        impressions, clicks, orders = int(metrics["impressions"]), int(metrics["clicks"]), int(metrics["orders"])
        spend, sales = Decimal(str(metrics["spend"])), Decimal(str(metrics["sales"]))
        ctr, cpc, cvr, acos = metrics.get("ctr"), metrics.get("cpc"), metrics.get("cvr"), metrics.get("acos")
        signals: list[str] = []
        wasted = spend >= self.thresholds.wasted_spend_threshold and (orders == 0 or sales == 0)
        if wasted:
            signals.extend(("WASTED_SPEND", "BID_DECREASE_CANDIDATE"))
        elif acos is not None and sales > 0 and Decimal(str(acos)) > self.thresholds.target_acos_percent:
            signals.extend(("HIGH_ACOS", "BID_DECREASE_CANDIDATE"))
        if impressions >= self.thresholds.min_impressions_for_ctr and ctr is not None and Decimal(str(ctr)) < self.thresholds.low_ctr_percent:
            signals.append("LOW_CTR")
        if clicks >= self.thresholds.min_clicks_for_cvr and cvr is not None and Decimal(str(cvr)) < self.thresholds.low_cvr_percent:
            signals.append("LOW_CVR")
        if clicks >= self.thresholds.min_clicks_for_cvr and cpc is not None and Decimal(str(cpc)) > self.thresholds.high_cpc_amount:
            signals.append("HIGH_CPC")
        profitable = orders > 0 and acos is not None and Decimal(str(acos)) < self.thresholds.target_acos_percent
        major_negative = any(code in signals for code in ("WASTED_SPEND", "HIGH_ACOS", "LOW_CVR", "HIGH_CPC"))
        if profitable and not major_negative:
            if scope_type == "search_term":
                signals.append("PROFITABLE_SEARCH_TERM")
                signals.append("KEYWORD_HARVEST_CANDIDATE")
            if scope_type in ("keyword", "campaign"):
                signals.append("BID_INCREASE_CANDIDATE")
        if scope_type == "search_term" and wasted:
            signals.append("NEGATIVE_KEYWORD_CANDIDATE")
        if not signals:
            signals.append("KEEP_STABLE")
        return tuple(dict.fromkeys(signals))