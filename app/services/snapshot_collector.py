"""Read-only paginated listing snapshot collector."""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
import logging
logger=logging.getLogger(__name__)
@dataclass(frozen=True)
class CollectionResult:
    started_at:datetime; finished_at:datetime; listings_fetched:int; snapshots_saved:int; changed_count:int; unchanged_count:int; failed_count:int; pages_processed:int; success:bool; errors:tuple[str,...]
    def public_dict(self):
        result=asdict(self); result["started_at"]=self.started_at.isoformat(); result["finished_at"]=self.finished_at.isoformat(); result["errors"]=list(self.errors); return result
class SnapshotCollector:
    def __init__(self,listing_service,repository): self._listing_service=listing_service; self._repository=repository
    def collect(self,seller_id,marketplace_id,page_size=10,max_pages=100):
        started=datetime.now(timezone.utc); fetched=saved=changed=unchanged=failed=pages=0; errors=[]; token=None; success=True
        for page_number in range(1,max(1,max_pages)+1):
            try: page=self._listing_service.get_listings(seller_id,marketplace_id,page_size,token)
            except Exception as error:
                logger.warning("snapshot page retrieval failed page=%s error_type=%s",page_number,type(error).__name__); errors.append("listing page retrieval failed"); success=False; break
            pages+=1; fetched+=len(page.listings); logger.info("snapshot page processed page=%s listings=%s",page_number,len(page.listings))
            for listing in page.listings:
                try: snapshot=self._repository.save_listing_snapshot(listing); saved+=1; changed+=int(snapshot.changed); unchanged+=int(not snapshot.changed)
                except Exception as error:
                    logger.warning("snapshot save failed page=%s error_type=%s",page_number,type(error).__name__); failed+=1; errors.append("listing snapshot save failed")
            token=page.next_token
            if not token: break
        finished=datetime.now(timezone.utc); result=CollectionResult(started,finished,fetched,saved,changed,unchanged,failed,pages,success,tuple(errors)); self._repository.save_snapshot_run(result); return result
