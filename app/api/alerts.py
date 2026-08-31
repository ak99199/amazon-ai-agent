"""Authenticated internal alert read and dismissal API."""
from fastapi import APIRouter,HTTPException,Query,Request
from app.alerts.models import ALERT_SEVERITIES,ALERT_STATUSES
from app.alerts.repository import AlertStorageConfigurationError,create_alert_repository
from app.config import ConfigurationError,require_dashboard_context
from app.security.auth import valid_csrf
router=APIRouter(prefix="/api/alerts",tags=["alerts"])
def _context_and_repository():
    context=require_dashboard_context();return context,create_alert_repository()
@router.get("")
def list_alerts(status:str|None=Query(None),severity:str|None=Query(None),limit:int=Query(50,ge=1,le=200)):
    if status and status not in ALERT_STATUSES:raise HTTPException(422,"Invalid alert status")
    if severity and severity not in ALERT_SEVERITIES:raise HTTPException(422,"Invalid alert severity")
    try:
        context,repository=_context_and_repository();alerts=repository.list_alerts(context.seller_id,context.marketplace_id,status,severity,limit);return {"alerts":[alert.public_dict() for alert in alerts],"new_count":repository.count_alerts(context.seller_id,context.marketplace_id,"new")}
    except (ConfigurationError,AlertStorageConfigurationError):raise HTTPException(503,"Alert storage is unavailable") from None
@router.post("/{alert_id}/dismiss")
def dismiss_alert(alert_id:str,request:Request):
    if not valid_csrf(request,request.headers.get("X-CSRF-Token")):raise HTTPException(403,"Invalid request")
    try:
        context,repository=_context_and_repository()
        if not repository.dismiss(context.seller_id,context.marketplace_id,alert_id):raise HTTPException(404,"Alert not found")
        return {"status":"dismissed"}
    except (ConfigurationError,AlertStorageConfigurationError):raise HTTPException(503,"Alert storage is unavailable") from None