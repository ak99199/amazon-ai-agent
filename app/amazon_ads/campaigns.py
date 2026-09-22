"""Read-only Sponsored Products campaign normalization."""
from datetime import date
from decimal import Decimal,InvalidOperation
from app.amazon_ads.ingestion_models import AdsCampaign
class SponsoredProductsCampaignsService:
    def __init__(self,client):self._client=client
    def list_campaigns(self,profile_id,max_pages=10):
        if not 1<=max_pages<=100:raise ValueError("Campaign page limit is invalid")
        items=[];cursor=None
        for _ in range(max_pages):
            body={"maxResults":100}
            if cursor:body["nextToken"]=cursor
            payload=self._client.post_read_only("/sp/campaigns/list",json=body,profile_id=profile_id,media_type="application/vnd.spCampaign.v3+json")
            page=payload if isinstance(payload,list) else payload.get("campaigns",[]) if isinstance(payload,dict) else []
            items.extend(page if isinstance(page,list) else [])
            cursor=payload.get("nextToken") if isinstance(payload,dict) else None
            if not cursor:break
        return [self._normalize(profile_id,item) for item in items if isinstance(item,dict)]
    @staticmethod
    def _normalize(profile_id,row):
        nested=row.get("budget") if isinstance(row.get("budget"),dict) else {}
        amount=nested.get("budget") if "budget" in row else row.get("dailyBudget")
        try:budget=Decimal(str(amount)) if amount is not None else None
        except (InvalidOperation,ValueError):budget=None
        parse_date=lambda value:date.fromisoformat(value[:10]) if isinstance(value,str) else None
        campaign_id=row.get("campaignId")
        if campaign_id is None:raise ValueError("Campaign row is invalid")
        return AdsCampaign(str(profile_id),str(campaign_id),row.get("name") or row.get("campaignName"),row.get("state") or row.get("status"),budget,nested.get("budgetType") if "budget" in row else row.get("budgetType"),row.get("targetingType"),parse_date(row.get("startDate")),parse_date(row.get("endDate")),str(row["portfolioId"]) if row.get("portfolioId") is not None else None)
