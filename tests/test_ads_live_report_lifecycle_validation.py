from datetime import datetime,timezone
import pytest
from app.amazon_ads.client import AdsApiClientError
from app.amazon_ads.config import AdsSettings
from app.amazon_ads.live_models import AdsLiveReportStatus
from app.amazon_ads.live_read import AdsLiveReadConfig
from app.amazon_ads.report_transport import AdsReportTransportError
from app.amazon_ads.reporting import SponsoredProductsReportingService
from app.services.ads_live_report_lifecycle_validation_service import AdsLiveReportLifecycleValidationService
from app.services.ads_production_readiness_service import AdsProductionReadinessService

NOW=datetime(2026,2,10,12,tzinfo=timezone.utc)
def readiness(approval="approved",settings=None,config=None):return AdsProductionReadinessService(settings or AdsSettings("id","secret","refresh","profile","FE"),config or AdsLiveReadConfig(True,False),approval)
class Transport:
 def __init__(self,statuses=("completed",),create_error=None,status_error=None,report_id="report"):self.statuses=list(statuses);self.create_error=create_error;self.status_error=status_error;self.report_id=report_id;self.creates=[];self.polls=[];self.downloads=[]
 def create(self,profile,definition):
  self.creates.append((profile,definition))
  if self.create_error:raise self.create_error
  return self.report_id
 def status(self,profile,report_id):
  self.polls.append((profile,report_id))
  if self.status_error:raise self.status_error
  return AdsLiveReportStatus(report_id,self.statuses.pop(0) if self.statuses else "processing","https://signed-secret")
 def download_rows(self,*args):self.downloads.append(args);raise AssertionError("download forbidden")
def run(transport=None,ready=None,confirm=True,max_polls=5,reporting=None):
 transport=transport or Transport();calls=[]
 def factory():calls.append(True);return transport,reporting or SponsoredProductsReportingService()
 result=AdsLiveReportLifecycleValidationService(ready or readiness(),factory,now=lambda:NOW,max_polls=max_polls).run(confirm)
 return result,transport,calls

@pytest.mark.parametrize("ready",[readiness("pending"),readiness("rejected"),readiness(config=AdsLiveReadConfig(False,False)),readiness(config=AdsLiveReadConfig(True,True)),readiness(settings=AdsSettings(None,"secret","refresh","profile","FE")),readiness(settings=AdsSettings("id","secret","refresh",None,"FE")),readiness(settings=AdsSettings("id","secret","refresh","profile","XX"))])
def test_readiness_blocks_before_dependency_construction(ready):
 result,transport,calls=run(ready=ready);assert result.status=="blocked_readiness" and calls==[] and transport.creates==[]
def test_confirmation_blocks_before_dependency_construction():
 result,transport,calls=run(confirm=False);assert result.status=="blocked_confirmation" and calls==[] and transport.creates==[]
def test_request_is_server_selected_bounded_historical_campaign_report_and_created_once():
 result,transport,_=run();definition=transport.creates[0][1]
 assert result.status=="success" and result.start_date=="2026-02-08" and result.end_date=="2026-02-09"
 assert len(transport.creates)==1 and definition["configuration"]["reportTypeId"]=="spCampaigns" and definition["configuration"]["timeUnit"]=="DAILY"
 assert definition["configuration"]["groupBy"]==["campaign"] and {"date","campaignId"}<=set(definition["configuration"]["columns"])
 assert result.report_id_present and result.download_ready and transport.downloads==[] and "signed" not in str(result.public_dict())
@pytest.mark.parametrize("statuses,expected,terminal",[(('pending','completed'),"success",True),(('processing','completed'),"success",True),(('failed',),"report_failed",True),(('cancelled',),"report_failed",True),(('unknown',),"validation_error",True)])
def test_status_lifecycle_is_normalized(statuses,expected,terminal):
 result,transport,_=run(Transport(statuses));assert result.status==expected and result.terminal is terminal and len(transport.polls)==len(statuses) and transport.downloads==[]
def test_poll_limit_is_exact_and_does_not_download():
 result,transport,_=run(Transport(("processing",)*9),max_polls=3);assert result.status=="poll_timeout" and result.poll_attempts==3 and len(transport.polls)==3 and transport.downloads==[]
@pytest.mark.parametrize("error,expected",[(AdsApiClientError(401,"raw Authorization"),"auth_error"),(AdsApiClientError(403,"raw refresh_token"),"auth_error"),(AdsApiClientError(429,"raw"),"rate_limited"),(AdsApiClientError(500,"raw"),"remote_error"),(TimeoutError("raw"),"remote_error")])
def test_creation_errors_are_safe(error,expected):
 result,_,_=run(Transport(create_error=error));assert result.status==expected and "raw" not in str(result.public_dict())
def test_missing_report_id_and_malformed_create_response_are_validation_errors():
 assert run(Transport(report_id=None))[0].status=="validation_error"
 assert run(Transport(create_error=AdsReportTransportError("raw body")))[0].status=="validation_error"
