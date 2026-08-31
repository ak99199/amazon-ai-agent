from app.amazon_ads.campaigns import SponsoredProductsCampaignsService
class Client:
 def __init__(self,p):self.p=p;self.calls=[]
 def get_profile_scoped(self,*a,**k):self.calls.append((a,k));return self.p
def test_campaigns_are_normalized_and_scoped():
 c=Client([{"campaignId":1,"name":"Name","dailyBudget":"10.50"},{"campaignId":2}]);rows=SponsoredProductsCampaignsService(c).list_campaigns("profile",2)
 assert len(rows)==2 and rows[0].campaign_id=="1" and str(rows[0].daily_budget)=="10.50" and c.calls[0][1]["profile_id"]=="profile"
def test_campaign_service_has_no_mutations():
 value=SponsoredProductsCampaignsService(Client([]));assert not any(hasattr(value,name) for name in ("create_campaign","update_campaign","archive_campaign","change_budget"))