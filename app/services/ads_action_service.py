"""Internal-only human review workflow for current deterministic Ads recommendations."""
from datetime import datetime, timezone
from app.amazon_ads.action_models import AdsRecommendationDecision, VALID_DECISION_STATUSES


class UnknownAdsRecommendationError(LookupError):
    pass


class AdsActionService:
    """Records human intent only; it never calls Amazon Ads or executes a change."""

    reviewable_statuses = frozenset({"approved", "rejected", "dismissed"})

    def __init__(self, recommendation_service, repository, now=None):
        self.recommendation_service = recommendation_service
        self.repository = repository
        self.now = now or (lambda: datetime.now(timezone.utc))

    def list_actions(self, seller_id, marketplace_id, profile_id, window=30, status=None, priority=None, limit=50):
        if status not in (None, *VALID_DECISION_STATUSES):
            raise ValueError("Unsupported Ads action status")
        recommendations = self.recommendation_service.get_recommendations(seller_id, marketplace_id, profile_id, window, priority=priority)
        actions = []
        for recommendation in recommendations:
            decision = self.repository.get_decision(seller_id, marketplace_id, profile_id, recommendation.recommendation_id)
            action = recommendation.public_dict()
            action["status"] = decision.status if decision else "pending"
            action["review_note"] = decision.review_note if decision else None
            action["reviewed_at"] = decision.reviewed_at.isoformat() if decision and decision.reviewed_at else None
            actions.append(action)
        if status:
            actions = [item for item in actions if item["status"] == status]
        ordering = {"pending": 0, "approved": 1, "rejected": 2, "dismissed": 3}
        actions.sort(key=lambda item: (ordering[item["status"]], {"critical":0,"high":1,"medium":2,"low":3}[item["priority"]], item["recommendation_id"]))
        counts = {value: sum(item["status"] == value for item in actions) for value in VALID_DECISION_STATUSES}
        return {"actions": actions[:max(1, min(limit, 200))], "count": len(actions), "pending_count": counts["pending"], "approved_count": counts["approved"], "rejected_count": counts["rejected"], "dismissed_count": counts["dismissed"], "window": window}

    def set_decision(self, seller_id, marketplace_id, profile_id, recommendation_id, status, review_note=None, review_source="dashboard", window=30):
        if status not in self.reviewable_statuses:
            raise ValueError("Unsupported Ads review decision")
        recommendation = next((item for item in self.recommendation_service.get_recommendations(seller_id, marketplace_id, profile_id, window) if item.recommendation_id == recommendation_id), None)
        if not recommendation:
            raise UnknownAdsRecommendationError("Ads recommendation is not available")
        note = self._note(review_note)
        timestamp = self.now()
        snapshot = {"recommendation_code": recommendation.recommendation_code, "priority": recommendation.priority, "confidence": recommendation.confidence, "window_days": recommendation.window_days, "scope_type": recommendation.scope_type, "scope_id": recommendation.scope_id, "metrics_snapshot": recommendation.public_dict()["metrics_snapshot"], "suggested_action": recommendation.suggested_action, "suggested_bid_direction": recommendation.suggested_bid_direction}
        decision = AdsRecommendationDecision(recommendation.recommendation_id, seller_id, marketplace_id, str(profile_id), recommendation.scope_type, recommendation.scope_id, recommendation.recommendation_code, recommendation.title, status, note, review_source, created_at=timestamp, updated_at=timestamp, reviewed_at=timestamp, recommendation_snapshot=snapshot)
        return self.repository.save_decision(decision)

    @staticmethod
    def _note(value):
        if value is None:
            return None
        note = str(value).strip()
        if not note:
            return None
        if len(note) > 1000:
            raise ValueError("Review note is too long")
        return note
