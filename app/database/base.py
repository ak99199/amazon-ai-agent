"""Common repository contract and storage backend factory."""
from os import getenv
from typing import Protocol
from app.amazon.models import Listing
class SnapshotRepository(Protocol):
    def save_listing_snapshot(self, listing: Listing): ...
    def get_latest_listing(self, seller_id: str, marketplace_id: str, asin: str): ...
    def get_listing_history(self, seller_id: str, marketplace_id: str, asin: str, limit: int = 30): ...
    def find_changed_listings(self, seller_id: str, marketplace_id: str, since_timestamp): ...
    def count_snapshots(self, seller_id: str, marketplace_id: str) -> int: ...
    def save_snapshot_run(self, result): ...
class StorageConfigurationError(Exception): pass
def create_snapshot_repository(backend=None):
    mode=backend or getenv("STORAGE_BACKEND","sqlite")
    if mode == "sqlite":
        from app.database.repository import ListingSnapshotRepository
        return ListingSnapshotRepository()
    if mode != "dynamodb": raise StorageConfigurationError("Snapshot storage is not configured")
    snapshots,runs=getenv("DYNAMODB_SNAPSHOTS_TABLE"),getenv("DYNAMODB_RUNS_TABLE")
    if not snapshots or not runs: raise StorageConfigurationError("Snapshot storage is not configured")
    try: import boto3
    except ImportError as error: raise StorageConfigurationError("DynamoDB support is unavailable") from error
    from app.database.dynamodb_repository import DynamoDbSnapshotRepository
    dynamodb=boto3.resource("dynamodb"); return DynamoDbSnapshotRepository(dynamodb.Table(snapshots),dynamodb.Table(runs))
