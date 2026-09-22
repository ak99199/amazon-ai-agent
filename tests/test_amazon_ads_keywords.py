import pytest
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.keywords import SponsoredProductsKeywordsService
class Client:
 def __init__(self):self.calls=[]
 def post_read_only(self,path,**kwargs):
  self.calls.append((path,kwargs))
  return {"keywords":[{"campaignId":"c","adGroupId":"g","keywordId":"k","keywordText":"word","matchType":"EXACT","bid":"1.25"}]} if "keywords" in path else {"targetingClauses":[{"targetId":"t","expression":"asin=1"}]}
def test_keywords_and_targets_are_read_only_and_normalized():
 client=Client();value=SponsoredProductsKeywordsService(client);keyword=value.list_keywords("p")[0];target=value.list_targets("p")[0]
 assert keyword.match_type=="EXACT" and str(keyword.bid)=="1.25" and target.target_id=="t" and target.target_expression=="asin=1" and not any(hasattr(value,name) for name in ("update_bid","archive_keyword","create_negative_keyword"))
 assert client.calls==[("/sp/keywords/list",{"json":{"maxResults":100},"profile_id":"p","media_type":"application/vnd.spKeyword.v3+json"}),("/sp/targets/list",{"json":{"maxResults":100},"profile_id":"p","media_type":"application/vnd.spTargetingClause.v3+json"})]

@pytest.mark.parametrize("method,path,key,media,identifier",[("list_keywords","/sp/keywords/list","keywords","spKeyword","keywordId"),("list_targets","/sp/targets/list","targetingClauses","spTargetingClause","targetId")])
def test_keyword_and_target_pagination_stops_at_max_pages(method,path,key,media,identifier):
 class Paged:
  def __init__(self):self.calls=[]
  def post_read_only(self,request_path,**kwargs):
   self.calls.append((request_path,kwargs))
   return {key:[{identifier:str(len(self.calls))}],"nextToken":"next" if len(self.calls)==1 else "more"}
 client=Paged();rows=getattr(SponsoredProductsKeywordsService(client),method)("p",2)
 assert len(rows)==2 and [getattr(row,"keyword_id" if identifier=="keywordId" else "target_id") for row in rows]==["1","2"]
 assert client.calls==[(path,{"json":{"maxResults":100},"profile_id":"p","media_type":f"application/vnd.{media}.v3+json"}),(path,{"json":{"maxResults":100,"nextToken":"next"},"profile_id":"p","media_type":f"application/vnd.{media}.v3+json"})]

def test_keyword_and_target_lists_preserve_client_error():
 class Broken:
  def post_read_only(self,*args,**kwargs):raise AdsApiClientError(429,"Amazon Ads rate limit reached",True)
 value=SponsoredProductsKeywordsService(Broken())
 for method in (value.list_keywords,value.list_targets):
  with pytest.raises(AdsApiClientError) as error:method("p")
  assert error.value.status_code==429
