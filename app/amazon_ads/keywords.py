"""Read-only Sponsored Products keyword and targeting normalization."""
from decimal import Decimal,InvalidOperation
from app.amazon_ads.ingestion_models import AdsKeyword
class SponsoredProductsKeywordsService:
    def __init__(self,client):self._client=client
    def list_keywords(self,profile_id,max_pages=10):return self._list(profile_id,"/sp/keywords","keyword",max_pages)
    def list_targets(self,profile_id,max_pages=10):return self._list(profile_id,"/sp/targets","target",max_pages)
    def _list(self,profile_id,path,kind,max_pages):
        if not 1<=max_pages<=100:raise ValueError("Keyword page limit is invalid")
        payload=self._client.get_profile_scoped(path,params={"maxPages":max_pages},profile_id=profile_id);items=payload if isinstance(payload,list) else payload.get(f"{kind}s",[]) if isinstance(payload,dict) else []
        return [self._normalize(profile_id,item,kind) for item in items if isinstance(item,dict)]
    @staticmethod
    def _normalize(profile_id,row,kind):
        bid=row.get("bid")
        try:bid=Decimal(str(bid)) if bid is not None else None
        except (InvalidOperation,ValueError):bid=None
        return AdsKeyword(str(profile_id),str(row["campaignId"]) if row.get("campaignId") is not None else None,str(row["adGroupId"]) if row.get("adGroupId") is not None else None,str(row["keywordId"]) if row.get("keywordId") is not None else None,row.get("keywordText") if isinstance(row.get("keywordText"),str) else None,row.get("matchType") if isinstance(row.get("matchType"),str) else None,row.get("state") if isinstance(row.get("state"),str) else None,bid,str(row["targetId"]) if row.get("targetId") is not None else None,row.get("expression") or row.get("targetExpression") if isinstance(row.get("expression") or row.get("targetExpression"),str) else None)