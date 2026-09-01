"""Bounded read/report request, poll, and normalized-download boundary."""
from gzip import GzipFile
from io import BytesIO
import json
from app.amazon_ads.client import AdsApiClientError,AdsDownloadLimitError
from app.amazon_ads.live_models import AdsLiveReportStatus
class AdsReportTransportError(Exception): pass
class AdsReportDownloadError(AdsReportTransportError): pass
class AdsReportDecompressionError(AdsReportTransportError): pass
class AdsReportParseError(AdsReportTransportError): pass
class AdsReportTransport:
    def __init__(self,client,max_attempts=5,sleeper=None):self.client=client;self.max_attempts=max(1,max_attempts);self.sleeper=sleeper or (lambda _:None)
    def create(self,profile_id,definition):
        payload=self.client.post_read_only("/reporting/reports",json=definition,profile_id=profile_id)
        report_id=payload.get("reportId") if isinstance(payload,dict) else None
        if not report_id: raise AdsReportTransportError("Amazon Ads report request was invalid")
        return str(report_id)
    def poll(self,profile_id,report_id):
        for attempt in range(self.max_attempts):
            result=self.status(profile_id,report_id);normalized=result.status
            if normalized in ("completed","failed","cancelled","unknown"): return result
            if attempt < self.max_attempts-1:self.sleeper(0)
        return AdsLiveReportStatus(report_id,"processing")
    def status(self,profile_id,report_id):
        payload=self.client.get_profile_scoped(f"/reporting/reports/{report_id}",profile_id=profile_id)
        status=str(payload.get("status","unknown")).lower() if isinstance(payload,dict) else "unknown"
        normalized={"success":"completed","completed":"completed","failure":"failed","failed":"failed","cancelled":"cancelled","processing":"processing","in_progress":"processing","requested":"pending","pending":"pending"}.get(status,"unknown")
        return AdsLiveReportStatus(report_id,normalized,payload.get("url") or payload.get("location") if isinstance(payload,dict) else None)
    def download_rows(self,profile_id,report_id,max_rows=10000):
        payload=self.client.get_profile_scoped(f"/reporting/reports/{report_id}/download",profile_id=profile_id)
        rows=payload if isinstance(payload,list) else payload.get("rows",[]) if isinstance(payload,dict) else []
        if not isinstance(rows,list):raise AdsReportTransportError("Amazon Ads report download was invalid")
        return [row for row in rows[:max_rows] if isinstance(row,dict)]
    def download_gzip_json(self,location,compressed_limit=1048576,decompressed_limit=5242880):
        if not isinstance(location,str) or not location:raise AdsReportDownloadError("Amazon Ads report location was unavailable")
        try:compressed=self.client.download_signed(location,compressed_limit)
        except AdsDownloadLimitError:raise AdsReportDownloadError("Amazon Ads report download exceeded the safety limit") from None
        except AdsApiClientError:raise
        except Exception:
            raise AdsReportDownloadError("Amazon Ads report download failed") from None
        if not isinstance(compressed,(bytes,bytearray)) or len(compressed)>compressed_limit:raise AdsReportDownloadError("Amazon Ads report download exceeded the safety limit")
        try:
            with GzipFile(fileobj=BytesIO(compressed)) as stream:decoded=stream.read(decompressed_limit+1)
        except (OSError,EOFError):raise AdsReportDecompressionError("Amazon Ads report gzip content was invalid") from None
        if len(decoded)>decompressed_limit:raise AdsReportDecompressionError("Amazon Ads report decompressed content exceeded the safety limit")
        try:payload=json.loads(decoded.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError):raise AdsReportParseError("Amazon Ads report JSON was invalid") from None
        if not isinstance(payload,list):raise AdsReportParseError("Amazon Ads report JSON shape was invalid")
        return payload,len(compressed),len(decoded)
