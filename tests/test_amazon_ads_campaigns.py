import pytest
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.campaigns import SponsoredProductsCampaignsService
class Client:
 def __init__(self,pages):self.pages=iter(pages);self.calls=[]
 def post_read_only(self,path,**kwargs):self.calls.append((path,kwargs));return next(self.pages)
def test_campaigns_are_normalized_and_scoped():
 c=Client([{"campaigns":[{"campaignId":1,"name":"Name","dailyBudget":"10.50"},{"campaignId":2}]}]);rows=SponsoredProductsCampaignsService(c).list_campaigns("profile",2)
 assert len(rows)==2 and rows[0].campaign_id=="1" and str(rows[0].daily_budget)=="10.50"
 assert c.calls==[("/sp/campaigns/list",{"json":{"maxResults":100},"profile_id":"profile","media_type":"application/vnd.spCampaign.v3+json"})]
def test_v3_nested_campaign_budget_is_normalized_without_changing_legacy_reader():
 row=SponsoredProductsCampaignsService._normalize("profile",{"campaignId":"1","budget":{"budget":15,"budgetType":"DAILY"}})
 assert row.daily_budget==15 and row.budget_type=="DAILY"
def test_campaign_list_pagination_stops_at_max_pages():
 c=Client([{"campaigns":[{"campaignId":"1","budget":{"budget":15,"budgetType":"DAILY"}}],"nextToken":"next"},{"campaigns":[{"campaignId":"2"}],"nextToken":"more"}])
 rows=SponsoredProductsCampaignsService(c).list_campaigns("profile",2)
 assert [row.campaign_id for row in rows]==["1","2"] and rows[0].daily_budget==15
 assert [call[1]["json"] for call in c.calls]==[{"maxResults":100},{"maxResults":100,"nextToken":"next"}]
 assert len(c.calls)==2
def test_campaign_list_preserves_client_error():
 class Broken:
  def post_read_only(self,*args,**kwargs):raise AdsApiClientError(401,"Amazon Ads authorization is invalid or expired")
 with pytest.raises(AdsApiClientError) as error:SponsoredProductsCampaignsService(Broken()).list_campaigns("profile")
 assert error.value.status_code==401
def test_campaign_service_has_no_mutations():
 value=SponsoredProductsCampaignsService(Client([]));assert not any(hasattr(value,name) for name in ("create_campaign","update_campaign","archive_campaign","change_budget"))
