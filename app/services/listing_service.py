class ListingService:
    def __init__(self,amazon_listings): self._amazon_listings=amazon_listings
    def get_listings(self,seller_id,marketplace_id,limit=10,page_token=None): return self._amazon_listings.search_listings(seller_id,marketplace_id,limit,page_token)
