"""Read-only search-term report normalization facade."""
from app.amazon_ads.reporting import SponsoredProductsReportingService
class SearchTermReportService:
    def __init__(self,reporting_service=None):self._reporting=reporting_service or SponsoredProductsReportingService()
    def normalize_rows(self,seller_id,marketplace_id,profile_id,rows):return self._reporting.normalize_rows(seller_id,marketplace_id,profile_id,rows,"SP")
    def normalize_row(self,seller_id,marketplace_id,profile_id,row):return self._reporting.normalize_row(seller_id,marketplace_id,profile_id,row,"SP")