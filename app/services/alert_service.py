"""Deterministic alert evaluation and optional notification delivery."""
from datetime import datetime, timezone
import logging
from app.alerts.models import Alert, alert_dedupe_key
from app.alerts.repository import new_alert_id
logger=logging.getLogger(__name__)
class AlertService:
    def __init__(self,repository,notification_provider=None): self._repository=repository; self._provider=notification_provider
    def evaluate(self,insights,generated_at=None):
        data=insights.public_dict() if hasattr(insights,"public_dict") else insights; current=data.get("current_listing") or {}; intelligence=data.get("intelligence") or {}; recommendations=data.get("recommendations") or {}; seller_id,marketplace_id,asin=data.get("seller_id"),data.get("marketplace_id"),data.get("asin")
        if not seller_id or not marketplace_id or not asin: return []
        status=(current.get("listing_status") or "").upper(); risk_score=int(intelligence.get("risk_score") or 0); flags=set(intelligence.get("risk_flags") or ()); priority=recommendations.get("priority") or "low"; action=recommendations.get("overall_action") or "MONITOR_LISTING"; now=generated_at or datetime.now(timezone.utc); candidates=[]
        if status and status not in ("ACTIVE","BUYABLE"): candidates.append(("LISTING_INACTIVE","high","Listing is inactive","The latest listing snapshot is not active.",action,{"status":status}))
        if risk_score>=70: candidates.append(("HIGH_RISK_LISTING","high","High-risk listing detected","Deterministic historical risk is high and needs seller review.",action,{"risk_score":risk_score}))
        if priority in ("critical","high"): candidates.append(("PRIORITY_RECOMMENDATION",priority,"High-priority seller action",recommendations.get("summary") or "A deterministic recommendation needs review.",action,{"priority":priority,"action":action}))
        if "RECENT_MAJOR_CHANGE" in flags: candidates.append(("RECENT_MAJOR_CHANGE","medium","Recent listing change","A meaningful listing change was detected recently.","INVESTIGATE_RECENT_CHANGE",{"flag":"RECENT_MAJOR_CHANGE"}))
        if "FULFILLMENT_UNSTABLE" in flags: candidates.append(("FULFILLMENT_INSTABILITY","high","Fulfillment setup changed","Historical fulfillment channel changes need review.","REVIEW_FULFILLMENT",{"flag":"FULFILLMENT_UNSTABLE"}))
        if "PRICE_VOLATILE" in flags and risk_score>=50: candidates.append(("PRICE_VOLATILITY","medium","Important price volatility","Historical price movement is high and should be reviewed manually.","REVIEW_PRICE_VOLATILITY",{"flag":"PRICE_VOLATILE","risk_score":risk_score}))
        return [Alert(new_alert_id(),seller_id,marketplace_id,asin,kind,severity,title,message,action_code,now,alert_dedupe_key(seller_id,marketplace_id,asin,kind,state)) for kind,severity,title,message,action_code,state in candidates]
    def process(self,insights,generated_at=None):
        stored=[]
        for alert in self.evaluate(insights,generated_at):
            if self._repository.get_by_dedupe_key(alert.seller_id,alert.marketplace_id,alert.dedupe_key): continue
            self._repository.save(alert); stored.append(alert)
            if self._provider:
                try: self._provider.send(alert); self._repository.mark_sent(alert.seller_id,alert.marketplace_id,alert.alert_id)
                except Exception: logger.warning("alert notification failed alert_id=%s provider=%s",alert.alert_id,type(self._provider).__name__)
        return stored