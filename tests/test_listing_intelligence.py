from datetime import datetime,timezone,timedelta
from app.amazon.models import Listing
from app.database.repository import ListingSnapshotRepository
from app.services.listing_intelligence_service import ListingIntelligenceService

def item(price="10",title="Title",status="ACTIVE",fulfillment="AMAZON_NA",seller="seller",market="market"):
    return Listing(seller,market,"SKU","B012345678",title=title,price=price,currency="INR",listing_status=status,fulfillment_channel=fulfillment)
def service(tmp_path): return ListingIntelligenceService(ListingSnapshotRepository(tmp_path/"intelligence.db"))
def save(repo,listing,when): repo._repository.save_listing_snapshot(listing,when)
def test_empty_and_single_snapshot(tmp_path):
    value=service(tmp_path); empty=value.analyze("seller","market","B012345678","all"); assert empty.snapshot_count == 0 and empty.data_confidence == "low"
    save(value,item(),datetime.now(timezone.utc)); single=value.analyze("seller","market","B012345678","all"); assert single.snapshot_count == 1 and single.price_direction == "flat"
def test_price_directions_and_changes(tmp_path):
    value=service(tmp_path); start=datetime.now(timezone.utc)-timedelta(days=10); save(value,item("10"),start); save(value,item("15"),start+timedelta(days=2)); up=value.analyze("seller","market","B012345678","all",start+timedelta(days=3)); assert up.price_direction == "up" and up.price_change_absolute == "5"
    save(value,item("5"),start+timedelta(days=4)); down=value.analyze("seller","market","B012345678","all",start+timedelta(days=5)); assert down.price_direction == "down"
def test_changes_risk_and_score_bounds(tmp_path):
    value=service(tmp_path); start=datetime.now(timezone.utc)-timedelta(days=40); save(value,item("10","Old","ACTIVE","A"),start); save(value,item("30","New","INACTIVE","B"),start+timedelta(days=35)); result=value.analyze("seller","market","B012345678","all",start+timedelta(days=36)); assert result.title_change_count == result.status_change_count == result.fulfillment_change_count == 1; assert "PRICE_VOLATILE" in result.risk_flags; assert 0<=result.stability_score<=100 and 0<=result.risk_score<=100 and 0<=result.opportunity_score<=100 and result.data_confidence == "medium"
def test_windows_and_scope_isolation(tmp_path):
    value=service(tmp_path); now=datetime.now(timezone.utc); save(value,item(seller="other"),now); save(value,item(),now-timedelta(days=40)); save(value,item("11"),now-timedelta(days=2)); assert value.analyze("seller","market","B012345678","7",now).snapshot_count == 1; assert value.analyze("seller","market","B012345678","30",now).snapshot_count == 1; assert value.analyze("seller","market","B012345678","90",now).snapshot_count == 2; assert value.analyze("other","market","B012345678","all",now).snapshot_count == 1
