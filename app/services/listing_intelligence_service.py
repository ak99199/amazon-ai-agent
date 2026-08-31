"""Deterministic intelligence derived from seller-scoped listing history."""
from dataclasses import asdict,dataclass
from datetime import datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
WINDOWS={"7":7,"30":30,"60":60,"90":90,"all":None}
@dataclass(frozen=True)
class ListingIntelligence:
    asin:str; seller_id:str; marketplace_id:str; first_seen:str|None; last_seen:str|None; days_tracked:int; snapshot_count:int; current_price:str|None; first_price:str|None; lowest_price:str|None; highest_price:str|None; average_price:str|None; price_change_absolute:str|None; price_change_percent:str|None; price_direction:str; title_change_count:int; status_change_count:int; fulfillment_change_count:int; brand_change_count:int; product_type_change_count:int; changed_snapshot_count:int; unchanged_snapshot_count:int; change_frequency:float; days_since_last_change:int|None; stability_score:int; risk_score:int; opportunity_score:int; data_confidence:str; risk_flags:tuple[str,...]; opportunity_flags:tuple[str,...]
    def public_dict(self):
        value=asdict(self); value["risk_flags"]=list(self.risk_flags); value["opportunity_flags"]=list(self.opportunity_flags); return value
class ListingIntelligenceService:
    def __init__(self,repository): self._repository=repository
    def analyze(self,seller_id,marketplace_id,asin,window="30",now=None):
        if window not in WINDOWS: raise ValueError("Unsupported intelligence window")
        now=now or datetime.now(timezone.utc); history=self._repository.get_listing_history(seller_id,marketplace_id,asin,100); history=[item for item in history if WINDOWS[window] is None or item.captured_at >= now-timedelta(days=WINDOWS[window])]; ordered=sorted(history,key=lambda item:(item.captured_at,item.id or 0))
        if not ordered: return self._empty(seller_id,marketplace_id,asin)
        first,last=ordered[0],ordered[-1]; days=(last.captured_at.date()-first.captured_at.date()).days; changes=self._transition_counts(ordered); prices=self._prices(ordered); changed=sum(item.changed for item in ordered); confidence=self._confidence(len(ordered),days); recent=self._days_since_change(ordered,now)
        stability=self._stability(len(ordered),days,changed,changes); risk,flags=self._risk(last,changes,prices,recent,confidence); opportunity,opportunities=self._opportunity(stability,last,confidence,flags)
        return ListingIntelligence(asin,seller_id,marketplace_id,first.captured_at.isoformat(),last.captured_at.isoformat(),days,len(ordered),prices["current"],prices["first"],prices["low"],prices["high"],prices["average"],prices["absolute"],prices["percent"],prices["direction"],changes["title"],changes["status"],changes["fulfillment"],changes["brand"],changes["product_type"],changed,len(ordered)-changed,round(changed/len(ordered),4),recent,stability,risk,opportunity,confidence,tuple(flags),tuple(opportunities))
    @staticmethod
    def _transition_counts(items):
        fields={"title":"title","status":"listing_status","fulfillment":"fulfillment_channel","brand":"brand","product_type":"product_type"}; return {key:sum(getattr(left,field)!=getattr(right,field) for left,right in zip(items,items[1:])) for key,field in fields.items()}
    @staticmethod
    def _prices(items):
        values=[]
        for item in items:
            try:
                if item.price is not None: values.append(Decimal(item.price))
            except (InvalidOperation,ValueError): pass
        if not values: return {key:None for key in ("current","first","low","high","average","absolute","percent")}|{"direction":"unknown"}
        first,current,low,high=values[0],values[-1],min(values),max(values); absolute=current-first; percent=None if first==0 else (absolute/first*100)
        return {"current":str(current),"first":str(first),"low":str(low),"high":str(high),"average":str(sum(values)/len(values)),"absolute":str(absolute),"percent":str(percent) if percent is not None else None,"direction":"up" if absolute>0 else "down" if absolute<0 else "flat"}
    @staticmethod
    def _confidence(count,days): return "high" if count>=10 and days>=30 else "medium" if (count>=4 and days>=7) or (count>=2 and days>=30) else "low"
    @staticmethod
    def _days_since_change(items,now):
        changed=[item for item in items if item.changed]; return (now.date()-changed[-1].captured_at.date()).days if changed else None
    @staticmethod
    def _stability(count,days,changed,changes):
        score=100-30*(changed/count)-min(20,changes["status"]*10)-min(15,changes["title"]*5)-min(15,changes["fulfillment"]*5)+min(15,days//7); return max(0,min(100,round(score)))
    @staticmethod
    def _risk(last,changes,prices,recent,confidence):
        score=0; flags=[]
        if (last.listing_status or "").upper() not in ("ACTIVE","BUYABLE"): score+=35; flags.append("STATUS_UNSTABLE")
        if changes["status"]: score+=min(25,changes["status"]*10); flags.append("STATUS_UNSTABLE")
        if changes["title"]: score+=min(15,changes["title"]*5); flags.append("TITLE_FREQUENTLY_CHANGED")
        if changes["fulfillment"]: score+=min(15,changes["fulfillment"]*5); flags.append("FULFILLMENT_UNSTABLE")
        try: volatile=prices["percent"] is not None and abs(Decimal(prices["percent"]))>=20
        except InvalidOperation: volatile=False
        if volatile: score+=20; flags.append("PRICE_VOLATILE")
        if recent is not None and recent<=7: score+=10; flags.append("RECENT_MAJOR_CHANGE")
        if confidence=="low": score+=10; flags.append("INSUFFICIENT_HISTORY")
        return max(0,min(100,score)),list(dict.fromkeys(flags))
    @staticmethod
    def _opportunity(stability,last,confidence,risk_flags):
        score=stability//2; flags=[]
        if (last.listing_status or "").upper() in ("ACTIVE","BUYABLE"): score+=20; flags.append("CONSISTENTLY_ACTIVE")
        if stability>=75: score+=15; flags.append("STABLE_LISTING")
        if confidence in ("medium","high"): score+=15; flags.append("SUFFICIENT_HISTORY")
        if not risk_flags: score+=10; flags.append("LOW_OPERATIONAL_RISK")
        return max(0,min(100,score)),flags
    @staticmethod
    def _empty(seller,marketplace,asin): return ListingIntelligence(asin,seller,marketplace,None,None,0,0,None,None,None,None,None,None,None,"unknown",0,0,0,0,0,0,0,0.0,None,0,10,0,"low",("INSUFFICIENT_HISTORY",),())

