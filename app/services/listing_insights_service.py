"""Consolidated read-only seller insights assembled from existing services."""
from dataclasses import asdict,dataclass
from datetime import datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from app.services.listing_intelligence_service import WINDOWS
@dataclass(frozen=True)
class ListingInsightsResult:
    asin:str; seller_id:str; marketplace_id:str; generated_at:str; window:str; current_listing:dict|None; history_summary:dict; intelligence:dict; recommendations:dict; explanation:dict
    def public_dict(self): return asdict(self)
class ListingInsightsService:
    def __init__(self,repository,intelligence_service,recommendation_service,explanation_service): self._repository=repository; self._intelligence=intelligence_service; self._recommendations=recommendation_service; self._explanations=explanation_service
    def get_insights(self,seller_id,marketplace_id,asin,window="30",now=None):
        if window not in WINDOWS: raise ValueError("Unsupported insights window")
        now=now or datetime.now(timezone.utc); latest=self._repository.get_latest_listing(seller_id,marketplace_id,asin); history=self._repository.get_listing_history(seller_id,marketplace_id,asin,100); days=WINDOWS[window]; filtered=[item for item in history if days is None or item.captured_at>=now-timedelta(days=days)]; intelligence=self._intelligence.analyze(seller_id,marketplace_id,asin,window,now); recommendation=self._recommendations.recommend(intelligence,now); explanation=self._explanations.explain(recommendation,now)
        return ListingInsightsResult(asin,seller_id,marketplace_id,now.isoformat(),window,self._current(latest),self._summary(filtered),intelligence.public_dict(),recommendation.public_dict(),explanation.public_dict())
    @staticmethod
    def _current(snapshot):
        if not snapshot: return None
        return {field:getattr(snapshot,field) if field!="captured_at" else snapshot.captured_at.isoformat() for field in ("sku","asin","title","brand","product_type","condition","listing_status","price","currency","fulfillment_channel","captured_at")}
    @staticmethod
    def _summary(history):
        if not history: return {"first_seen":None,"last_seen":None,"days_tracked":0,"snapshot_count":0,"changed_snapshot_count":0,"unchanged_snapshot_count":0,"last_change_at":None,"price_min":None,"price_max":None,"price_average":None}
        ordered=sorted(history,key=lambda item:(item.captured_at,item.id or 0)); prices=[]
        for item in ordered:
            try:
                if item.price is not None: prices.append(Decimal(item.price))
            except (InvalidOperation,ValueError): pass
        changed=[item for item in ordered if item.changed]; return {"first_seen":ordered[0].captured_at.isoformat(),"last_seen":ordered[-1].captured_at.isoformat(),"days_tracked":(ordered[-1].captured_at.date()-ordered[0].captured_at.date()).days,"snapshot_count":len(ordered),"changed_snapshot_count":len(changed),"unchanged_snapshot_count":len(ordered)-len(changed),"last_change_at":changed[-1].captured_at.isoformat() if changed else None,"price_min":str(min(prices)) if prices else None,"price_max":str(max(prices)) if prices else None,"price_average":str(sum(prices)/len(prices)) if prices else None}
