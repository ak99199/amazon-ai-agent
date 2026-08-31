"""Deterministic decimal Ads metrics calculated from normalized totals."""
from decimal import Decimal
class AdsMetricsService:
    @staticmethod
    def calculate(impressions,clicks,spend,orders,units,sales):
        impressions=int(impressions);clicks=int(clicks);orders=int(orders);units=int(units);spend=Decimal(str(spend));sales=Decimal(str(sales));percent=lambda numerator,denominator:None if not denominator else numerator/denominator*Decimal("100")
        return {"impressions":impressions,"clicks":clicks,"spend":spend,"orders":orders,"units":units,"sales":sales,"ctr":percent(Decimal(clicks),Decimal(impressions)),"cpc":None if not clicks else spend/Decimal(clicks),"cvr":percent(Decimal(orders),Decimal(clicks)),"acos":percent(spend,sales),"roas":None if not spend else sales/spend}
    def aggregate(self,rows):
        totals={"impressions":0,"clicks":0,"spend":Decimal("0"),"orders":0,"units":0,"sales":Decimal("0")}
        for row in rows:
            for field in totals:totals[field]+=getattr(row,field)
        return self.calculate(**totals)