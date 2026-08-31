import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.jobs.listing_snapshot_job import run_listing_snapshot_job
import argparse
parser=argparse.ArgumentParser(description="Collect read-only Amazon listing snapshots")
parser.add_argument("--max-pages",type=int,default=100)
parser.add_argument("--page-size",type=int,default=10)
args=parser.parse_args(); result=run_listing_snapshot_job(args.max_pages,args.page_size)
print(f"fetched={result.listings_fetched} saved={result.snapshots_saved} changed={result.changed_count} unchanged={result.unchanged_count} failed={result.failed_count} pages={result.pages_processed} success={result.success}")
