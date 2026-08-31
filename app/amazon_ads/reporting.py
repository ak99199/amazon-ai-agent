"""Version-isolated Sponsored Products report definitions and row normalizer."""
from datetime import date
from decimal import Decimal,InvalidOperation
from app.amazon_ads.report_models import AdsPerformanceDaily,AdsReportRequest
class AdsReportNormalizationError(Exception):pass
_REPORT_LEVELS={"campaign":(("campaignId",),),"ad_group":(("campaignId","adGroupId"),),"keyword":(("campaignId","adGroupId","keywordId"),),"targeting":(("campaignId","adGroupId","targetId"),),"search_term":(("campaignId","adGroupId","searchTerm"),)}
_DEFAULT_COLUMNS=("impressions","clicks","cost","purchases14d","unitsSold14d","sales14d")
class SponsoredProductsReportingService:
    def build_request(self,report_level,start_date,end_date,columns=None):
        if report_level not in _REPORT_LEVELS:raise ValueError("Unsupported Sponsored Products report level")
        if start_date>end_date:raise ValueError("Report date range is invalid")
        return AdsReportRequest("SP",report_level,start_date,end_date,tuple(columns or _DEFAULT_COLUMNS),_REPORT_LEVELS[report_level][0])
    def normalize_rows(self,seller_id,marketplace_id,profile_id,rows,ad_product="SP"):
        if not isinstance(rows,list):raise AdsReportNormalizationError("Amazon Ads report payload is invalid")
        return [self.normalize_row(seller_id,marketplace_id,profile_id,row,ad_product) for row in rows if isinstance(row,dict)]
    def normalize_row(self,seller_id,marketplace_id,profile_id,row,ad_product="SP"):
        report_date=self._date(self._value(row,"date","reportDate"));return AdsPerformanceDaily(seller_id,marketplace_id,str(profile_id),report_date,ad_product,self._text(row,"campaignId","campaign_id"),self._text(row,"campaignName","campaign_name"),self._text(row,"adGroupId","ad_group_id"),self._text(row,"adGroupName","ad_group_name"),self._text(row,"keywordId","keyword_id"),self._text(row,"keywordText","keyword_text","keyword"),self._text(row,"matchType","match_type"),self._text(row,"targetId","target_id"),self._text(row,"targetExpression","target_expression"),self._text(row,"searchTerm","search_term"),self._text(row,"currency","currencyCode"),self._count(row,"impressions"),self._count(row,"clicks"),self._money(row,"cost","spend"),self._count(row,"purchases14d","orders","attributedOrders14d"),self._count(row,"unitsSold14d","units","attributedUnitsOrdered14d"),self._money(row,"sales14d","sales","attributedSales14d"))
    @staticmethod
    def _value(row,*names):
        for name in names:
            if name in row:return row[name]
        return None
    def _text(self,row,*names):
        value=self._value(row,*names);return str(value) if value is not None else None
    def _date(self,value):
        if isinstance(value,date):return value
        if not isinstance(value,str):raise AdsReportNormalizationError("Amazon Ads report date is invalid")
        try:return date.fromisoformat(value[:10])
        except ValueError as error:raise AdsReportNormalizationError("Amazon Ads report date is invalid") from error
    def _count(self,row,*names):
        value=self._value(row,*names)
        if value is None or value=="":return 0
        try:number=Decimal(str(value))
        except (InvalidOperation,ValueError) as error:raise AdsReportNormalizationError("Amazon Ads report metric is invalid") from error
        if not number.is_finite() or number!=number.to_integral_value():raise AdsReportNormalizationError("Amazon Ads report metric is invalid")
        return int(number)
    def _money(self,row,*names):
        value=self._value(row,*names)
        if value is None or value=="":return Decimal("0")
        try:number=Decimal(str(value))
        except (InvalidOperation,ValueError) as error:raise AdsReportNormalizationError("Amazon Ads monetary metric is invalid") from error
        if not number.is_finite():raise AdsReportNormalizationError("Amazon Ads monetary metric is invalid")
        return number