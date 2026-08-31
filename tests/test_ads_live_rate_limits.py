from app.amazon_ads.read_adapters import SponsoredProductsReadAdapter
class Client:
 def __init__(self):self.calls=0
 def get_profile_scoped(self,path,params=None,profile_id=None):
  self.calls+=1
  return {"adGroups":[{"adGroupId":self.calls,"campaignId":"campaign","name":"Name"}],"nextToken":"more" if self.calls==1 else None}
def test_live_adapter_pagination_is_bounded_and_normalized():
 client=Client(); rows=SponsoredProductsReadAdapter(client,max_pages=2).ad_groups("profile")
 assert len(rows)==2 and rows[0].ad_group_id=="1" and client.calls==2
