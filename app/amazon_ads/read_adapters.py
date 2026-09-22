"""Version-isolated, read-only Sponsored Products adapters with bounded pagination."""
from decimal import Decimal, InvalidOperation
from app.amazon_ads.campaigns import SponsoredProductsCampaignsService
from app.amazon_ads.keywords import SponsoredProductsKeywordsService
from app.amazon_ads.live_models import AdsLiveAdGroup, AdsLiveTarget

class SponsoredProductsReadAdapter:
    _MEDIA_TYPES={"campaigns":"application/vnd.spCampaign.v3+json","adGroups":"application/vnd.spAdGroup.v3+json","keywords":"application/vnd.spKeyword.v3+json","targetingClauses":"application/vnd.spTargetingClause.v3+json"}
    def __init__(self,client,max_pages=10,page_size=100): self.client=client; self.max_pages=max(1,min(max_pages,100));self.page_size=max(1,min(page_size,100))
    def campaigns(self,profile_id): return [SponsoredProductsCampaignsService._normalize(profile_id,item) for item in self._pages("/sp/campaigns/list",profile_id,"campaigns") if isinstance(item,dict)]
    def first_campaign_page(self,profile_id,max_results=10):return self._first_page("/sp/campaigns/list",profile_id,"campaigns",max_results,10)
    def first_ad_group_page(self,profile_id,max_results=20):return self._first_page("/sp/adGroups/list",profile_id,"adGroups",max_results,20)
    def first_keyword_page(self,profile_id,max_results=25):return self._first_page("/sp/keywords/list",profile_id,"keywords",max_results,25)
    def first_target_page(self,profile_id,max_results=25):return self._first_page("/sp/targets/list",profile_id,"targetingClauses",max_results,25)
    def keywords(self,profile_id): return [SponsoredProductsKeywordsService._normalize(profile_id,item,"keyword") for item in self._pages("/sp/keywords/list",profile_id,"keywords") if isinstance(item,dict)]
    def targets(self,profile_id):
        return [self._target(item) for item in self._pages("/sp/targets/list",profile_id,"targetingClauses") if isinstance(item,dict) and item.get("targetId") is not None]
    def ad_groups(self,profile_id):
        return [self._ad_group(item) for item in self._pages("/sp/adGroups/list",profile_id,"adGroups") if isinstance(item,dict) and item.get("adGroupId") is not None and item.get("campaignId") is not None]
    def _pages(self,path,profile_id,key):
        items=[]; cursor=None
        for _ in range(self.max_pages):
            body={"maxResults":self.page_size}
            if cursor: body["nextToken"]=cursor
            payload=self.client.post_read_only(path,json=body,profile_id=profile_id,media_type=self._MEDIA_TYPES[key])
            page=payload if isinstance(payload,list) else payload.get(key,[]) if isinstance(payload,dict) else []
            items.extend(page if isinstance(page,list) else [])
            cursor=payload.get("nextToken") if isinstance(payload,dict) else None
            if not cursor: break
        return items
    def _first_page(self,path,profile_id,key,max_results,limit):
        size=max(1,min(int(max_results),limit));payload=self.client.post_read_only(path,json={"maxResults":size},profile_id=profile_id,media_type=self._MEDIA_TYPES[key])
        rows=payload if isinstance(payload,list) else payload.get(key,[]) if isinstance(payload,dict) else None
        return rows[:size] if isinstance(rows,list) else None
    @staticmethod
    def _money(value):
        try:return Decimal(str(value)) if value is not None else None
        except (InvalidOperation,ValueError):return None
    @staticmethod
    def _ad_group(row): return AdsLiveAdGroup(str(row["adGroupId"]),str(row["campaignId"]),row.get("name") or row.get("adGroupName"),row.get("state") or row.get("status"),SponsoredProductsReadAdapter._money(row.get("defaultBid")))
    @staticmethod
    def _target(row): return AdsLiveTarget(str(row["targetId"]),str(row["campaignId"]) if row.get("campaignId") is not None else None,str(row["adGroupId"]) if row.get("adGroupId") is not None else None,row["expression"] if "expression" in row else row.get("targetExpression"),row.get("resolvedExpression") if isinstance(row.get("resolvedExpression"),str) else None,row.get("state") or row.get("status"),SponsoredProductsReadAdapter._money(row.get("bid")))


