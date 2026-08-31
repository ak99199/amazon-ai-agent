"""Internal-only manual trigger for read-only snapshot collection."""
from fastapi import APIRouter,HTTPException,Query
from app.config import ConfigurationError
from app.jobs.listing_snapshot_job import run_listing_snapshot_job
router=APIRouter(prefix="/api/internal",tags=["internal"])
@router.post("/listings/snapshots/run")
def run_listing_snapshots(max_pages:int=Query(100,ge=1,le=100),page_size:int=Query(10,ge=1,le=20)):
    """Internal route: protect with authentication before production deployment."""
    try: return run_listing_snapshot_job(max_pages,page_size).public_dict()
    except ConfigurationError: raise HTTPException(503,"Amazon listing connection is not configured") from None
