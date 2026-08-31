"""Safe notification providers for normalized internal alerts."""
import logging
from os import getenv
from typing import Protocol
from app.alerts.models import Alert
logger=logging.getLogger(__name__)
def alerts_enabled(): return getenv("ALERTS_ENABLED","false").lower()=="true"
class NotificationProvider(Protocol):
    def send(self,alert:Alert)->None: ...
class LogNotificationProvider:
    def send(self,alert:Alert)->None: logger.info("alert notification sent alert_id=%s alert_type=%s severity=%s",alert.alert_id,alert.alert_type,alert.severity)
class SNSNotificationProvider:
    def __init__(self,topic_arn:str,client=None):self._topic_arn=topic_arn;self._client=client
    def send(self,alert:Alert)->None:
        if not self._client:
            import boto3
            self._client=boto3.client("sns")
        self._client.publish(TopicArn=self._topic_arn,Subject=alert.title[:100],Message=alert.message)
def notification_provider_from_environment()->NotificationProvider|None:
    if not alerts_enabled():return None
    provider=getenv("ALERT_NOTIFICATION_PROVIDER","").lower()
    if provider=="log":return LogNotificationProvider()
    if provider=="sns":
        topic_arn=getenv("ALERT_SNS_TOPIC_ARN")
        return SNSNotificationProvider(topic_arn) if topic_arn else None
    return None