"""Connects the bounded report transport to the existing normalized reporting service."""
class AdsLiveReportService:
    def __init__(self,transport,reporting_service,max_rows=10000):self.transport=transport;self.reporting_service=reporting_service;self.max_rows=max(1,max_rows)
    def request_poll_download(self,profile_id,definition):
        report_id=self.transport.create(profile_id,definition); status=self.transport.poll(profile_id,report_id)
        if status.status!="completed":return status,[]
        return status,self.transport.download_rows(profile_id,report_id,self.max_rows)
    def normalized_rows(self,seller_id,marketplace_id,profile_id,definition):
        status,rows=self.request_poll_download(profile_id,definition)
        return status,self.reporting_service.normalize_rows(seller_id,marketplace_id,profile_id,rows)
