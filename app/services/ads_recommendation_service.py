"""Read-only, deterministic Amazon Ads recommendations from historical rows."""
from collections import defaultdict
from datetime import datetime, timezone
from app.amazon_ads.recommendation_models import AdsRecommendation
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_metrics_service import AdsMetricsService
from app.services.ads_signal_service import AdsSignalService
from app.services.ads_rule_version_resolver import AdsRuleVersionResolver


_PRIORITY = {
    "WASTED_SPEND": "high", "HIGH_ACOS": "high", "BID_DECREASE_CANDIDATE": "high",
    "LOW_CTR": "medium", "LOW_CVR": "medium", "HIGH_CPC": "medium",
    "NEGATIVE_KEYWORD_CANDIDATE": "medium", "PROFITABLE_SEARCH_TERM": "medium",
    "KEYWORD_HARVEST_CANDIDATE": "medium", "BID_INCREASE_CANDIDATE": "medium",
    "MONITOR_PERFORMANCE": "low", "KEEP_STABLE": "low", "INSUFFICIENT_DATA": "low",
    "BUDGET_PRESSURE": "medium",
}
_TITLES = {
    "INSUFFICIENT_DATA": "Wait for more Ads history", "MONITOR_PERFORMANCE": "Monitor performance",
    "HIGH_ACOS": "Review high advertising cost", "LOW_CTR": "Review low click-through rate",
    "LOW_CVR": "Review low conversion rate", "HIGH_CPC": "Review high cost per click",
    "WASTED_SPEND": "Review spend without sales", "PROFITABLE_SEARCH_TERM": "Review profitable search term",
    "KEYWORD_HARVEST_CANDIDATE": "Consider keyword harvest", "NEGATIVE_KEYWORD_CANDIDATE": "Consider negative keyword review",
    "BID_DECREASE_CANDIDATE": "Consider lowering bid", "BID_INCREASE_CANDIDATE": "Consider raising bid",
    "BUDGET_PRESSURE": "Review budget pressure", "KEEP_STABLE": "Keep Ads performance stable",
}
_ACTIONS = {
    "INSUFFICIENT_DATA": "Continue collecting read-only historical Ads data before changing anything.",
    "KEEP_STABLE": "Continue monitoring; human review is still required.",
    "BID_DECREASE_CANDIDATE": "A seller may review whether a lower bid is appropriate; no bid is changed.",
    "BID_INCREASE_CANDIDATE": "A seller may review whether a higher bid is appropriate; no bid is changed.",
    "NEGATIVE_KEYWORD_CANDIDATE": "A seller may review the term for a negative keyword; no keyword is created.",
    "KEYWORD_HARVEST_CANDIDATE": "A seller may review this term for keyword research; no keyword is created.",
}


class AdsRecommendationService:
    """Uses only repository data and never invokes Amazon Ads APIs or mutations."""

    allowed_windows = (7, 14, 30, 60, 90)

    def __init__(self, repository: AdsPerformanceRepository, metrics: AdsMetricsService | None = None, signals: AdsSignalService | None = None, now=None, rule_version_resolver: AdsRuleVersionResolver | None = None):
        self.repository = repository
        self.metrics = metrics or AdsMetricsService()
        self.signals = signals
        self.rule_version_resolver = rule_version_resolver if rule_version_resolver is not None else (None if signals is not None else AdsRuleVersionResolver(repository))
        self.now = now or (lambda: datetime.now(timezone.utc))

    def get_profile_recommendations(self, seller_id, marketplace_id, profile_id, window=30, **filters):
        return self.get_recommendations(seller_id, marketplace_id, profile_id, window, **filters)

    def get_campaign_recommendations(self, seller_id, marketplace_id, profile_id, campaign_id=None, window=30, **filters):
        return self.get_recommendations(seller_id, marketplace_id, profile_id, window, scope_type="campaign", campaign_id=campaign_id, **filters)

    def get_keyword_recommendations(self, seller_id, marketplace_id, profile_id, keyword_id=None, window=30, **filters):
        return self.get_recommendations(seller_id, marketplace_id, profile_id, window, scope_type="keyword", keyword_id=keyword_id, **filters)

    def get_search_term_recommendations(self, seller_id, marketplace_id, profile_id, search_term=None, window=30, **filters):
        return self.get_recommendations(seller_id, marketplace_id, profile_id, window, scope_type="search_term", search_term=search_term, **filters)

    def get_recommendations(self, seller_id, marketplace_id, profile_id, window=30, scope_type=None, campaign_id=None, keyword_id=None, search_term=None, priority=None, reference_date=None):
        if window not in self.allowed_windows:
            raise ValueError("Unsupported Ads recommendation window")
        if scope_type not in (None, "campaign", "keyword", "search_term"):
            raise ValueError("Unsupported Ads recommendation scope")
        resolved = self.rule_version_resolver.resolve(seller_id, marketplace_id, profile_id) if self.rule_version_resolver else None
        signals = AdsSignalService(resolved.thresholds) if resolved else self.signals
        rows = self.repository.list_window(seller_id, marketplace_id, profile_id, window, reference_date, campaign_id=campaign_id, keyword_id=keyword_id, search_term=search_term)
        scopes = (scope_type,) if scope_type else ("campaign", "keyword", "search_term")
        result: list[AdsRecommendation] = []
        for current_scope in scopes:
            for scope_id, scope_rows in self._groups(rows, current_scope).items():
                metrics = self.metrics.aggregate(scope_rows)
                days = len({row.date for row in scope_rows})
                confidence = signals.confidence(metrics, days)
                label = self._label(scope_rows[0], current_scope, scope_id)
                for code in signals.codes(metrics, days, current_scope):
                    recommendation = AdsRecommendation(
                        seller_id=seller_id, marketplace_id=marketplace_id, profile_id=str(profile_id),
                        scope_type=current_scope, scope_id=scope_id, scope_label=label,
                        recommendation_code=code, priority=_PRIORITY[code], confidence=confidence,
                        title=_TITLES[code], summary=self._summary(code, metrics, days),
                        reason=self._reason(code, metrics, days), window_days=window,
                        metrics_snapshot=metrics, suggested_action=_ACTIONS.get(code, "Review the normalized historical metrics with a human; no Amazon change is made."),
                        suggested_bid_direction="decrease" if code == "BID_DECREASE_CANDIDATE" else ("increase" if code == "BID_INCREASE_CANDIDATE" else None),
                        created_at=self.now(),
                        rule_version_id=resolved.rule_version_id if resolved else None,
                        rule_version_name=resolved.rule_version_name if resolved else None,
                        rule_version_source=resolved.source if resolved else None,
                    )
                    if priority is None or recommendation.priority == priority:
                        result.append(recommendation)
        return sorted(result, key=lambda item: ({"critical": 0, "high": 1, "medium": 2, "low": 3}[item.priority], item.scope_type, item.scope_label, item.recommendation_code))

    @staticmethod
    def _groups(rows, scope_type):
        groups = defaultdict(list)
        for row in rows:
            value = {"campaign": row.campaign_id, "keyword": row.keyword_id, "search_term": row.search_term}[scope_type]
            if value:
                groups[str(value)].append(row)
        return groups

    @staticmethod
    def _label(row, scope_type, scope_id):
        labels = {"campaign": row.campaign_name, "keyword": row.keyword_text, "search_term": row.search_term}
        return labels.get(scope_type) or scope_id

    @staticmethod
    def _summary(code, metrics, days):
        return f"{code.replace('_', ' ').title()} based on {days} day(s), {metrics['clicks']} click(s), and {metrics['orders']} order(s)."

    @staticmethod
    def _reason(code, metrics, days):
        values = {"ACOS": metrics.get("acos"), "CTR": metrics.get("ctr"), "CVR": metrics.get("cvr"), "CPC": metrics.get("cpc")}
        metric = next((name for name in values if name in code and values[name] is not None), None)
        if metric:
            return f"Aggregated {metric} is {values[metric]} across {days} observed day(s)."
        return f"The rule evaluated normalized totals: spend {metrics['spend']}, sales {metrics['sales']}, and {metrics['orders']} order(s)."
