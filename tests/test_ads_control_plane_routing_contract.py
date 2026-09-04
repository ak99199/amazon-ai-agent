from app.database.ads_control_plane_base import CONTROL_PLANE_METHODS
from app.database.ads_control_plane_dynamodb_repository import DynamoDbAdsControlPlaneRepository

def test_every_routed_control_plane_method_has_dynamodb_implementation():
 missing=sorted(name for name in CONTROL_PLANE_METHODS if not callable(getattr(DynamoDbAdsControlPlaneRepository,name,None)))
 assert missing==[]
