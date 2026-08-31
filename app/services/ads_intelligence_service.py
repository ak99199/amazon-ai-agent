"""Read-only, deterministic Amazon Ads performance intelligence."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from app.amazon_ads.config import AdsSettings
from app.amazon_ads.intelligence_models import AdsIntelligenceSummary
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.services.ads_action_service import AdsActionService
from app.services.ads_metrics_service import AdsMetricsService
from app.services.ads_recommendation_service import AdsRecommendationService
from app.services.ads_sync_gate_service import AdsSyncGateService
from app.services.ads_sync_observability_service import AdsSyncObservabilityService


class AdsIntelligenceService:
    """Combines local, normalized Ads history only; it never calls or changes Amazon."""

    allowed_windows = AdsRecommendationService.allowed_windows

    def __init__(self, repository, metrics=None, recommendation_service=None, action_service=None, sync_observability_service=None, today=None):
        self.repository = repository
        self.metrics = metrics or AdsMetricsService()
        self.recommendation_service = recommendation_service or AdsRecommendationService(repository, self.metrics)
        self.action_service = action_service or AdsActionService(self.recommendation_service, repository)
        self.sync_observability_service = sync_observability_service
        self.today = today or date.today

    def get(self, seller_id, marketplace_id, profile_id, window=30, limit=10, reference_date=None):
        if window not in self.allowed_windows:
            raise ValueError("Unsupported Ads intelligence window")
        if not 1 <= limit <= 50:
            raise ValueError("Ads intelligence limit is invalid")
        end_date = reference_date or self.today()
        start_date = end_date - timedelta(days=window - 1)
        rows = self.repository.list_window(seller_id, marketplace_id, profile_id, window, end_date)
        previous_rows = self.repository.list_rows(seller_id, marketplace_id, profile_id, start_date - timedelta(days=window), start_date - timedelta(days=1), today=end_date)
        totals = self.metrics.aggregate(rows)
        previous = self.metrics.aggregate(previous_rows)
        recommendations = self.recommendation_service.get_recommendations(seller_id, marketplace_id, profile_id, window, reference_date=end_date)
        actions = self.action_service.list_actions(seller_id, marketplace_id, profile_id, window, limit=200)
        recommendation_codes = self._codes(recommendations)
        return AdsIntelligenceSummary(
            window, start_date, end_date,
            self._summary(totals, rows, recommendations, actions, profile_id),
            self._trend(rows), self._comparison(totals, previous),
            self._rank(self._groups(rows, "campaign"), "campaign", recommendation_codes, limit, weak=False),
            self._rank(self._groups(rows, "campaign"), "campaign", recommendation_codes, limit, weak=True),
            self._rank(self._groups(rows, "keyword"), "keyword", recommendation_codes, limit, weak=False),
            self._rank(self._groups(rows, "keyword"), "keyword", recommendation_codes, limit, weak=True),
            self._terms(self._groups(rows, "search_term"), recommendation_codes, limit, profitable=True),
            self._terms(self._groups(rows, "search_term"), recommendation_codes, limit, profitable=False),
            self._recommendation_summary(recommendations), self._decision_summary(actions),
            self._sync_health(seller_id, marketplace_id, profile_id),
        )

    def _summary(self, metrics, rows, recommendations, actions, profile_id):
        return {
            "totals": metrics,
            "campaign_count": len(self._groups(rows, "campaign")),
            "keyword_count": len(self._groups(rows, "keyword")),
            "search_term_count": len(self._groups(rows, "search_term")),
            "recommendation_count": len(recommendations),
            "high_priority_recommendation_count": sum(item.priority in ("high", "critical") for item in recommendations),
            "pending_decision_count": actions["pending_count"],
            "approved_decision_count": actions["approved_count"],
            "rejected_decision_count": actions["rejected_count"],
            "dismissed_decision_count": actions["dismissed_count"],
            "profile_id": str(profile_id) if profile_id is not None else None,
        }

    def _trend(self, rows):
        by_day = defaultdict(list)
        for row in rows:
            by_day[row.date].append(row)
        return [{"date": day, **self.metrics.aggregate(by_day[day])} for day in sorted(by_day)]

    @staticmethod
    def _change(current, previous):
        if previous == 0:
            return None
        return (current - previous) / previous * Decimal("100")

    def _comparison(self, current, previous):
        return {
            "spend_change_percent": self._change(current["spend"], previous["spend"]),
            "sales_change_percent": self._change(current["sales"], previous["sales"]),
            "orders_change_percent": self._change(Decimal(current["orders"]), Decimal(previous["orders"])),
            "acos_change_percent": None if current["acos"] is None or previous["acos"] is None else self._change(current["acos"], previous["acos"]),
            "roas_change_percent": None if current["roas"] is None or previous["roas"] is None else self._change(current["roas"], previous["roas"]),
        }

    @staticmethod
    def _groups(rows, scope):
        field = {"campaign": "campaign_id", "keyword": "keyword_id", "search_term": "search_term"}[scope]
        groups = defaultdict(list)
        for row in rows:
            value = getattr(row, field)
            if value:
                groups[str(value)].append(row)
        return groups

    @staticmethod
    def _codes(recommendations):
        result = defaultdict(set)
        for item in recommendations:
            result[(item.scope_type, item.scope_id)].add(item.recommendation_code)
        return result

    def _record(self, scope, scope_id, rows, codes):
        first = rows[0]
        metrics = self.metrics.aggregate(rows)
        fields = {
            "campaign": {"campaign_id": scope_id, "campaign_name": first.campaign_name},
            "keyword": {"keyword_id": scope_id, "keyword_text": first.keyword_text, "match_type": first.match_type, "campaign_id": first.campaign_id, "ad_group_id": first.ad_group_id},
            "search_term": {"search_term": scope_id, "campaign_id": first.campaign_id, "ad_group_id": first.ad_group_id},
        }
        return {**fields[scope], **metrics, "recommendation_codes": sorted(codes.get((scope, scope_id), set()))}

    def _rank(self, groups, scope, codes, limit, weak):
        records = [self._record(scope, key, value, codes) for key, value in groups.items()]
        weak_codes = {"WASTED_SPEND", "HIGH_ACOS", "LOW_CVR", "HIGH_CPC", "BID_DECREASE_CANDIDATE"}
        if weak:
            records = [item for item in records if weak_codes.intersection(item["recommendation_codes"])]
            return sorted(records, key=lambda item: (-item["spend"], -(item["acos"] if item["acos"] is not None else Decimal("-1")), str(item.get(f"{scope}_id", ""))))[:limit]
        return sorted(records, key=lambda item: (-item["sales"], -(item["roas"] if item["roas"] is not None else Decimal("-1")), str(item.get(f"{scope}_id", ""))))[:limit]

    def _terms(self, groups, codes, limit, profitable):
        records = [self._record("search_term", key, value, codes) for key, value in groups.items()]
        desired = {"PROFITABLE_SEARCH_TERM", "KEYWORD_HARVEST_CANDIDATE"} if profitable else {"WASTED_SPEND", "NEGATIVE_KEYWORD_CANDIDATE"}
        records = [item for item in records if desired.intersection(item["recommendation_codes"])]
        return sorted(records, key=lambda item: ((-item["sales"], item["search_term"]) if profitable else (-item["spend"], item["search_term"])))[:limit]

    @staticmethod
    def _recommendation_summary(recommendations):
        return {"total": len(recommendations), "by_code": dict(sorted(Counter(item.recommendation_code for item in recommendations).items())), "by_priority": dict(sorted(Counter(item.priority for item in recommendations).items())), "by_scope_type": dict(sorted(Counter(item.scope_type for item in recommendations).items()))}

    @staticmethod
    def _decision_summary(actions):
        total = actions["count"]
        reviewed = actions["approved_count"] + actions["rejected_count"] + actions["dismissed_count"]
        return {"pending": actions["pending_count"], "approved": actions["approved_count"], "rejected": actions["rejected_count"], "dismissed": actions["dismissed_count"], "approval_rate": None if reviewed == 0 else Decimal(actions["approved_count"]) / Decimal(reviewed) * Decimal("100"), "rejection_rate": None if reviewed == 0 else Decimal(actions["rejected_count"]) / Decimal(reviewed) * Decimal("100"), "approved_is_not_executed": True, "total": total}

    def _sync_health(self, seller_id, marketplace_id, profile_id):
        try:
            service = self.sync_observability_service
            if service is None:
                settings = AdsSettings.from_environment()
                gate = AdsSyncGateService(settings, self.repository, AdsLiveReadConfig.from_environment())
                service = AdsSyncObservabilityService(self.repository, gate)
            result = service.get(seller_id, marketplace_id, profile_id)
            return {"health_status": result.health_status, "last_attempt": result.latest_sync, "last_success": result.latest_success, "last_failure": result.latest_failure, "recent_success_rate": result.success_rate_recent}
        except Exception:
            return {"health_status": "unavailable", "last_attempt": None, "last_success": None, "last_failure": None, "recent_success_rate": None}