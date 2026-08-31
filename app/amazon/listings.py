from dataclasses import dataclass
from app.amazon.models import Listing
@dataclass(frozen=True)
class ListingPage: listings:list[Listing]; next_token:str|None
class AmazonListingsService:
    def __init__(self,client): self._client=client
    def search_listings(self,seller_id,marketplace_id,page_size=10,page_token=None):
        params={"marketplaceIds":marketplace_id,"includedData":"summaries,attributes,offers,fulfillmentAvailability","pageSize":max(1,min(page_size,20))}
        if page_token: params["pageToken"]=page_token
        payload=self._client.get(f"listings/2021-08-01/items/{seller_id}",params); items=payload.get("items",[]) if isinstance(payload.get("items",[]),list) else []
        return ListingPage([Listing.from_amazon(item,seller_id,marketplace_id) for item in items if isinstance(item,dict)],payload.get("nextToken") if isinstance(payload.get("nextToken"),str) else None)
