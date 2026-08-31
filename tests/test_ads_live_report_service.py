from app.amazon_ads.report_transport import AdsReportTransport
from app.services.ads_live_report_service import AdsLiveReportService

class Client:
 def __init__(self):self.polls=0
 def post_read_only(self,*args,**kwargs):return {"reportId":"report"}
 def get_profile_scoped(self,path,**kwargs):
  self.polls+=1
  if self.polls==1:return {"status":"processing"}
  if self.polls==2:return {"status":"completed","location":"safe"}
  return [{"date":"2026-01-01"}]
class Reporting:
 def normalize_rows(self,*args):return ["normalized"]
def test_live_report_transport_is_bounded_and_mockable():
 client=Client(); service=AdsLiveReportService(AdsReportTransport(client,max_attempts=3),Reporting())
 status,rows=service.request_poll_download("profile",{})
 assert status.status=="completed" and rows==[{"date":"2026-01-01"}]
 assert service.normalized_rows("s","m","p",{})[1]==["normalized"]
