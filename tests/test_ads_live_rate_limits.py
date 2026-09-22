from app.amazon_ads.read_adapters import SponsoredProductsReadAdapter
class Client:
 def __init__(self):self.calls=[]
 def post_read_only(self,path,json=None,profile_id=None,media_type=None):
  self.calls.append((path,json,profile_id,media_type))
  return {"adGroups":[{"adGroupId":len(self.calls),"campaignId":"campaign","name":"Name"}],"nextToken":"more" if len(self.calls)==1 else None}
def test_live_adapter_pagination_is_bounded_and_normalized():
 client=Client(); rows=SponsoredProductsReadAdapter(client,max_pages=2).ad_groups("profile")
 assert len(rows)==2 and rows[0].ad_group_id=="1"
 assert client.calls==[("/sp/adGroups/list",{"maxResults":100},"profile","application/vnd.spAdGroup.v3+json"),("/sp/adGroups/list",{"maxResults":100,"nextToken":"more"},"profile","application/vnd.spAdGroup.v3+json")]
