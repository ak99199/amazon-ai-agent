import gzip,json
from datetime import datetime,timezone
import pytest
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_models import AdsLiveReportStatus
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.report_transport import AdsReportTransport,AdsReportDownloadError,AdsReportDecompressionError,AdsReportParseError
from app.amazon_ads.reporting import SponsoredProductsReportingService
from app.services.ads_live_report_lifecycle_validation_service import AdsLiveReportLifecycleValidationService
from app.services.ads_live_report_download_validation_service import AdsLiveReportDownloadValidationService
from app.services.ads_production_readiness_service import AdsProductionReadinessService

NOW=datetime(2026,2,10,12,tzinfo=timezone.utc)
def readiness(approval="approved",settings=None,config=None):return AdsProductionReadinessService(settings or AdsSettings("id","secret","refresh","profile","FE"),config or AdsLiveReadConfig(True,False),approval)
def row(**changes):return {"date":"2026-02-08","campaignId":"c1","impressions":"10","clicks":"2","cost":"1.25","purchases14d":"1","unitsSold14d":"1","sales14d":"4.50"}|changes
class Transport:
 def __init__(self,statuses=("completed",),rows=None,error=None):self.statuses=list(statuses);self.rows=[] if rows is None else rows;self.error=error;self.creates=[];self.polls=[];self.downloads=[]
 def create(self,profile,definition):self.creates.append((profile,definition));return "report"
 def status(self,profile,report):self.polls.append((profile,report));return AdsLiveReportStatus(report,self.statuses.pop(0),"https://signed-secret")
 def download_gzip_json(self,location,*limits):
  self.downloads.append((location,limits))
  if self.error:raise self.error
  return self.rows,100,200
def run(transport=None,ready=None,confirm=True,max_polls=5,row_limit=100):
 transport=transport or Transport(rows=[row()]);calls=[];reporting=SponsoredProductsReportingService()
 def factory():calls.append(True);return transport,reporting
 lifecycle=AdsLiveReportLifecycleValidationService(ready or readiness(),factory,now=lambda:NOW,max_polls=max_polls)
 return AdsLiveReportDownloadValidationService(lifecycle,reporting,row_limit=row_limit).run(confirm),transport,calls

@pytest.mark.parametrize("ready",[readiness("pending"),readiness("rejected"),readiness(config=AdsLiveReadConfig(False,False)),readiness(config=AdsLiveReadConfig(True,True)),readiness(settings=AdsSettings(None,"secret","refresh","profile","FE")),readiness(settings=AdsSettings("id","secret","refresh",None,"FE")),readiness(settings=AdsSettings("id","secret","refresh","profile","XX"))])
def test_gates_make_zero_dependency_and_download_calls(ready):
 result,transport,calls=run(ready=ready);assert result.status=="blocked_readiness" and calls==[] and transport.downloads==[]
def test_confirmation_false_makes_zero_dependency_and_download_calls():
 result,transport,calls=run(confirm=False);assert result.status=="blocked_confirmation" and calls==[] and transport.downloads==[]
def test_completed_lifecycle_creates_once_downloads_once_and_validates():
 result,transport,_=run();assert result.status=="success" and len(transport.creates)==1 and len(transport.downloads)==1 and result.rows_valid==1 and result.rows_invalid==0
 assert "signed" not in str(result.public_dict()) and "c1" not in str(result.public_dict())
@pytest.mark.parametrize("statuses,expected",[(('processing','processing'),"poll_timeout"),(('failed',),"report_failed"),(('cancelled',),"report_failed"),(('unknown',),"validation_error")])
def test_noncompleted_lifecycle_never_downloads(statuses,expected):
 result,transport,_=run(Transport(statuses,rows=[row()]),max_polls=len(statuses));assert result.status==expected and transport.downloads==[]
@pytest.mark.parametrize("error,expected",[(AdsReportDownloadError("raw"),"download_error"),(AdsReportDecompressionError("raw"),"decompression_error"),(AdsReportParseError("raw"),"parse_error"),(TimeoutError("raw"),"remote_error")])
def test_download_decode_and_parse_failures_are_safe(error,expected):
 result,_,_=run(Transport(rows=[row()],error=error));assert result.status==expected and "raw" not in str(result.public_dict())
def test_empty_report_is_valid_and_large_report_is_truncated():
 empty,_,_=run(Transport(rows=[]));large,_,_=run(Transport(rows=[row(date="2026-02-08",campaignId=f"c{i}") for i in range(101)]))
 assert empty.status=="valid_empty" and large.status=="success" and large.rows_validated==100 and large.rows_truncated
def test_malformed_numeric_date_and_duplicate_grain_rows_are_isolated():
 rows=[row(),row(campaignId="c2",cost="NaN"),row(campaignId="c3",sales14d="Infinity"),row(campaignId="c4",clicks="1.5"),row(campaignId="c5",cost="bad"),row(campaignId="c6",impressions="-1"),row(campaignId="c7",date="2026-02-07"),row()]
 result,_,_=run(Transport(rows=rows));assert result.status=="partial_valid" and result.rows_valid==1 and result.rows_invalid==7

class DownloadClient:
 def __init__(self,payload):self.payload=payload;self.calls=[]
 def download_signed(self,location,limit):self.calls.append((location,limit));return self.payload
def test_transport_downloads_and_parses_valid_gzip_array():
 client=DownloadClient(gzip.compress(json.dumps([row()]).encode()));payload,compressed,decompressed=AdsReportTransport(client).download_gzip_json("signed",1024,4096);assert payload==[row()] and compressed>0 and decompressed>0 and len(client.calls)==1
@pytest.mark.parametrize("payload,error",[(b"not-gzip",AdsReportDecompressionError),(gzip.compress(b"not-json"),AdsReportParseError),(gzip.compress(b"{}"),AdsReportParseError)])
def test_transport_rejects_invalid_gzip_json_and_shape(payload,error):
 with pytest.raises(error):AdsReportTransport(DownloadClient(payload)).download_gzip_json("signed",1024,4096)
def test_transport_rejects_compressed_and_decompressed_limit_overflow():
 with pytest.raises(AdsReportDownloadError):AdsReportTransport(DownloadClient(b"x"*11)).download_gzip_json("signed",10,100)
 with pytest.raises(AdsReportDecompressionError):AdsReportTransport(DownloadClient(gzip.compress(b"[]"+b" "*100))).download_gzip_json("signed",1024,10)
