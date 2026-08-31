"""Seller-wide deterministic aggregation of existing listing insights."""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
@dataclass(frozen=True)
class PortfolioInsightsResult:
    seller_id:str; marketplace_id:str; generated_at:str; window:str; total_listings:int; active_listings:int; inactive_listings:int; high_risk_count:int; medium_risk_count:int; low_risk_count:int; insufficient_history_count:int; recently_changed_count:int; stable_count:int; average_risk_score:float; average_opportunity_score:float; average_stability_score:float; listings:tuple[dict,...]
    def public_dict(self):
        value=asdict(self); value["listings"]=list(self.listings); return value
class PortfolioInsightsService:
    def __init__(self,repository,insights_service): self._repository=repository; self._insights=insights_service
    def get_portfolio(self,seller_id,marketplace_id,window="30",sort="risk_desc",priority=None,status=None,confidence=None,changed_recently=None,min_risk_score=None,limit=50,now=None):
        now=now or datetime.now(timezone.utc); records=[]
        for asin in self._repository.list_tracked_asins(seller_id,marketplace_id):
            result=self._insights.get_insights(seller_id,marketplace_id,asin,window,now); current=result.current_listing or {}; intelligence=result.intelligence; recommendation=result.recommendations
            record={"asin":asin,"sku":current.get("sku"),"title":current.get("title"),"listing_status":current.get("listing_status"),"current_price":current.get("price"),"currency":current.get("currency"),"captured_at":current.get("captured_at"),"risk_score":intelligence["risk_score"],"opportunity_score":intelligence["opportunity_score"],"stability_score":intelligence["stability_score"],"data_confidence":intelligence["data_confidence"],"overall_action":recommendation["overall_action"],"action_reason":recommendation["summary"],"priority":recommendation["priority"],"risk_flags":intelligence["risk_flags"],"opportunity_flags":intelligence["opportunity_flags"],"days_tracked":intelligence["days_tracked"],"snapshot_count":intelligence["snapshot_count"],"days_since_last_change":intelligence["days_since_last_change"]}
            if priority and record["priority"]!=priority: continue
            if status and record["listing_status"]!=status: continue
            if confidence and record["data_confidence"]!=confidence: continue
            if changed_recently is not None and ((record["days_since_last_change"] is not None and record["days_since_last_change"]<=7)!=changed_recently): continue
            if min_risk_score is not None and record["risk_score"]<min_risk_score: continue
            records.append(record)
        key={"risk_desc":lambda x:(-x["risk_score"],x["asin"]),"opportunity_desc":lambda x:(-x["opportunity_score"],x["asin"]),"stability_desc":lambda x:(-x["stability_score"],x["asin"]),"recent_change":lambda x:(x["days_since_last_change"] if x["days_since_last_change"] is not None else 10**9,x["asin"])}.get(sort)
        if key is None: raise ValueError("Unsupported portfolio sort")
        records=sorted(records,key=key)[:max(1,min(limit,200))]; total=len(records); active=sum((x["listing_status"] or "").upper() in ("ACTIVE","BUYABLE") for x in records); risk=lambda low,high:sum(low<=x["risk_score"]<=high for x in records)
        average=lambda field:round(sum(x[field] for x in records)/total,2) if total else 0.0
        return PortfolioInsightsResult(seller_id,marketplace_id,now.isoformat(),window,total,active,total-active,risk(70,100),risk(30,69),risk(0,29),sum(x["data_confidence"]=="low" for x in records),sum(x["days_since_last_change"] is not None and x["days_since_last_change"]<=7 for x in records),sum(x["stability_score"]>=75 for x in records),average("risk_score"),average("opportunity_score"),average("stability_score"),tuple(records))
