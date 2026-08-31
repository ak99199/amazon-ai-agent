from app.amazon_ads.keywords import SponsoredProductsKeywordsService
class Client:
 def get_profile_scoped(self,path,**kwargs):return [{"campaignId":"c","adGroupId":"g","keywordId":"k","keywordText":"word","matchType":"EXACT","bid":"1.25"}] if "keywords" in path else [{"targetId":"t","expression":"asin=1"}]
def test_keywords_and_targets_are_read_only_and_normalized():
 value=SponsoredProductsKeywordsService(Client());keyword=value.list_keywords("p")[0];target=value.list_targets("p")[0]
 assert keyword.match_type=="EXACT" and str(keyword.bid)=="1.25" and target.target_id=="t" and target.target_expression=="asin=1" and not any(hasattr(value,name) for name in ("update_bid","archive_keyword","create_negative_keyword"))