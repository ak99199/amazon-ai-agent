"""Read-only human-review analytics for deterministic Ads recommendations."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from os import getenv

from app.amazon_ads.effectiveness_models import AdsRecommendationEffectivenessSummary, AdsRecommendationFeedbackRecord


class AdsRecommendationEffectivenessService:
    allowed_windows = (7, 14, 30, 60, 90)

    def __init__(self, repository, now=None, min_reviewed_sample=None, high_rejection_percent=None, high_approval_percent=None):
        self.repository = repository
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.min_reviewed_sample = int(min_reviewed_sample if min_reviewed_sample is not None else getenv("AMAZON_ADS_EFFECTIVENESS_MIN_REVIEWED_SAMPLE", "5"))
        self.high_rejection_percent = Decimal(str(high_rejection_percent if high_rejection_percent is not None else getenv("AMAZON_ADS_EFFECTIVENESS_HIGH_REJECTION_PERCENT", "70")))
        self.high_approval_percent = Decimal(str(high_approval_percent if high_approval_percent is not None else getenv("AMAZON_ADS_EFFECTIVENESS_HIGH_APPROVAL_PERCENT", "70")))

    def get(self, seller_id, marketplace_id, profile_id, window=30):
        if window not in self.allowed_windows:
            raise ValueError("Unsupported Ads effectiveness window")
        end = self.now()
        start = end - timedelta(days=window)
        reviewed = self.repository.list_effectiveness_decisions(seller_id, marketplace_id, profile_id, start)
        pending = [item for item in self.repository.list_effectiveness_decisions(seller_id, marketplace_id, profile_id) if item.status == "pending"]
        return self._summary(window, start, end, [*reviewed, *pending])

    def feedback(self, seller_id, marketplace_id, profile_id, window=30, limit=100):
        if window not in self.allowed_windows or not 1 <= limit <= 500:
            raise ValueError("Invalid Ads feedback request")
        since = self.now() - timedelta(days=window)
        decisions = self.repository.list_effectiveness_decisions(seller_id, marketplace_id, profile_id, since, limit)
        return [self._feedback_record(item) for item in decisions if item.status in ("approved", "rejected", "dismissed")]

    def _summary(self, window, start, end, decisions):
        grouped = self._group(decisions, lambda item: item.recommendation_code)
        by_code = [self._counts("recommendation_code", key, value) for key, value in grouped.items()]
        by_code.sort(key=lambda item: (-item["reviewed"], item["recommendation_code"]))
        snapshots = [(item, item.recommendation_snapshot) for item in decisions if item.recommendation_snapshot]
        by_priority = self._group_summary(snapshots, "priority")
        by_scope = self._group_summary([(item, {"scope_type": item.scope_type}) for item in decisions], "scope_type")
        total = self._counts(None, None, decisions)
        repeated = [item["recommendation_code"] for item in by_code if item["reviewed"] >= self.min_reviewed_sample and item["rejection_rate"] is not None and item["rejection_rate"] >= self.high_rejection_percent]
        approved = [item["recommendation_code"] for item in by_code if item["reviewed"] >= self.min_reviewed_sample and item["approval_rate"] is not None and item["approval_rate"] >= self.high_approval_percent]
        return AdsRecommendationEffectivenessSummary(window, start, end, total["reviewed"], total["pending"], total["approved"], total["rejected"], total["dismissed"], total["approval_rate"], total["rejection_rate"], total["dismissal_rate"], by_code, by_priority, by_scope, repeated, approved, total["reviewed"])

    def _group_summary(self, values, key):
        grouped = defaultdict(list)
        for decision, snapshot in values:
            value = snapshot.get(key) if snapshot else None
            if value is not None:
                grouped[str(value)].append(decision)
        result = [self._counts(key, group_key, records) for group_key, records in grouped.items()]
        return sorted(result, key=lambda item: (-item["reviewed"], item[key]))

    @staticmethod
    def _group(decisions, field):
        grouped = defaultdict(list)
        for decision in decisions:
            grouped[str(field(decision))].append(decision)
        return grouped

    @staticmethod
    def _counts(label, value, decisions):
        counts = {status: sum(item.status == status for item in decisions) for status in ("pending", "approved", "rejected", "dismissed")}
        reviewed = counts["approved"] + counts["rejected"] + counts["dismissed"]
        rate = lambda count: None if reviewed == 0 else Decimal(count) / Decimal(reviewed) * Decimal("100")
        result = {"total": len(decisions), **counts, "reviewed": reviewed, "approval_rate": rate(counts["approved"]), "rejection_rate": rate(counts["rejected"]), "dismissal_rate": rate(counts["dismissed"])}
        if label is not None: result[label] = value
        return result

    @staticmethod
    def _feedback_record(decision):
        snapshot = decision.recommendation_snapshot
        return AdsRecommendationFeedbackRecord(decision.recommendation_id, decision.stable_decision_id, decision.seller_id, decision.marketplace_id, decision.profile_id, decision.recommendation_code, decision.scope_type, decision.scope_id, snapshot.get("priority") if snapshot else None, snapshot.get("confidence") if snapshot else None, snapshot.get("window_days") if snapshot else None, decision.status, bool(decision.review_note), decision.reviewed_at, snapshot.get("metrics_snapshot") if snapshot else None, snapshot.get("suggested_action") if snapshot else None, snapshot.get("suggested_bid_direction") if snapshot else None, snapshot is not None)