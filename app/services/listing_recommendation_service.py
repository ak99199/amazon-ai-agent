"""Deterministic, human-review-only listing recommendations."""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from app.services.listing_intelligence_service import ListingIntelligence
@dataclass(frozen=True)
class Recommendation:
    action:str; priority:str; reason:str; evidence:dict; safe_next_step:str
@dataclass(frozen=True)
class RecommendationResult:
    asin:str; seller_id:str; marketplace_id:str; generated_at:str; overall_action:str; priority:str; recommendations:tuple[Recommendation,...]; summary:str; data_confidence:str; risk_score:int; opportunity_score:int; stability_score:int
    def public_dict(self):
        value=asdict(self); value["recommendations"]=[asdict(item) for item in self.recommendations]; return value
class ListingRecommendationService:
    _RULES={"INSUFFICIENT_HISTORY":("WAIT_FOR_MORE_DATA","Collect more historical observations before changing anything.","Continue read-only monitoring until confidence improves."),"STATUS_UNSTABLE":("CHECK_LISTING_STATUS","Listing status has been unstable.","Review status and suppression details in Seller Central manually."),"PRICE_VOLATILE":("REVIEW_PRICE_VOLATILITY","Historical price movement is high.","Review price history and pricing policy manually; do not automate a change."),"TITLE_FREQUENTLY_CHANGED":("REVIEW_TITLE","Title has changed repeatedly.","Review title consistency and listing quality manually."),"FULFILLMENT_UNSTABLE":("REVIEW_FULFILLMENT","Fulfillment channel has changed.","Review fulfillment configuration manually."),"RECENT_MAJOR_CHANGE":("INVESTIGATE_RECENT_CHANGE","A meaningful listing change occurred recently.","Compare the latest snapshot with the prior observation before acting.")}
    def recommend(self,intelligence:ListingIntelligence,generated_at=None):
        generated=(generated_at or datetime.now(timezone.utc)).isoformat(); recommendations=[]
        for flag in intelligence.risk_flags:
            rule=self._RULES.get(flag)
            if rule:
                action,reason,next_step=rule; recommendations.append(Recommendation(action,self._priority_for(flag,intelligence),reason,{"risk_flag":flag,"risk_score":intelligence.risk_score,"snapshot_count":intelligence.snapshot_count},next_step))
        if not recommendations and intelligence.snapshot_count==0: recommendations.append(Recommendation("WAIT_FOR_MORE_DATA","low","No historical snapshots are available.",{"snapshot_count":0,"data_confidence":intelligence.data_confidence},"Run read-only snapshot collection and monitor the listing."))
        if not recommendations and intelligence.risk_score<=20 and intelligence.stability_score>=75: recommendations.append(Recommendation("KEEP_STABLE","low","The listing is historically stable with low operational risk.",{"stability_score":intelligence.stability_score,"risk_score":intelligence.risk_score},"Continue read-only monitoring; use human review before any change."))
        if not recommendations: recommendations.append(Recommendation("MONITOR_LISTING","medium","The listing needs continued observation.",{"risk_score":intelligence.risk_score,"data_confidence":intelligence.data_confidence},"Continue read-only monitoring and review future trends."))
        priority=self._overall_priority(recommendations); overall=recommendations[0].action
        return RecommendationResult(intelligence.asin,intelligence.seller_id,intelligence.marketplace_id,generated,overall,priority,tuple(recommendations),self._summary(recommendations),intelligence.data_confidence,intelligence.risk_score,intelligence.opportunity_score,intelligence.stability_score)
    @staticmethod
    def _priority_for(flag,value):
        if flag=="STATUS_UNSTABLE" and value.risk_score>=70: return "critical"
        if flag in ("STATUS_UNSTABLE","PRICE_VOLATILE","FULFILLMENT_UNSTABLE") or value.risk_score>=50: return "high"
        if flag=="INSUFFICIENT_HISTORY": return "low"
        return "medium"
    @staticmethod
    def _overall_priority(items):
        order={"low":0,"medium":1,"high":2,"critical":3}; return max(items,key=lambda item:order[item.priority]).priority
    @staticmethod
    def _summary(items): return " ".join(item.reason for item in items)
