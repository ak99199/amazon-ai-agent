# Amazon Listing Data Engine

## Step 7 — Listing Data Engine

This project exposes a read-only Amazon Listings Items API layer:

`GET /api/listings` → Listing Service → Listings API service → generic SP-API client → LWA authentication → Amazon.

The India SP-API endpoint is `https://sellingpartnerapi-eu.amazon.com`; set `AMAZON_MARKETPLACE_ID=A21TJRUUN4KGV` in your local `.env`. Required variables are `AMAZON_SP_API_CLIENT_ID`, `AMAZON_SP_API_CLIENT_SECRET`, `AMAZON_SP_REFRESH_TOKEN`, `AMAZON_SELLER_ID`, and `AMAZON_MARKETPLACE_ID`.

`GET /health` returns `{"status":"ok"}`. `GET /api/listings?limit=10` returns a bounded normalized listing page and optional `next_token`. It is read-only and supports pagination. Raw Amazon responses, secrets, access tokens, authorization headers, and buyer/customer PII are excluded from API responses.

Never commit `.env`. The existing proof scripts remain separate from pytest; pytest only collects mocked tests under `tests/` and therefore makes no real Amazon API calls.

## Local commands

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
python -m compileall -q app
python -m pytest -q
```

## Step 8 — Historical Listing Data

Step 8 stores normalized listing snapshots in local SQLite at `data/amazon_ai_agent.db`. The `listing_snapshots` schema records the seller and marketplace scope, capture time, normalized listing fields, a deterministic SHA-256 listing hash, and whether the snapshot changed from the previous snapshot for the same seller, marketplace, and ASIN.

Every repository lookup requires `seller_id` and `marketplace_id`, preventing seller or marketplace data from mixing. The history service provides first/last seen dates, price change, title/status change flags, snapshot count, and tracked days. The internal `save_current_listings()` service operation persists already-normalized listings only; it never writes to Amazon.

`GET /api/listings/{asin}/history?limit=30` returns normalized snapshot history and its trend summary. It contains no credentials, headers, raw Amazon payload, or buyer data. Historical data lets a future AI component query changes through internal services rather than Amazon directly.

SQLite is appropriate for this local MVP. A multi-user SaaS deployment should migrate the same seller-scoped schema and repository contract to PostgreSQL with managed backups and access controls.

## Step 9 — Scheduled Snapshot Collection

The read-only snapshot collector fetches Listings Items API pages, normalizes them through the existing listing service, and saves every observation to SQLite. It preserves the existing `changed` flag so unchanged observations remain useful checkpoints for reliable days-tracked calculations. One safe `snapshot_runs` row records counts and a sanitized error summary for every run; it never stores secrets or raw API payloads.

Run one collection manually:

```powershell
python scripts/collect_listing_snapshots.py --max-pages 100 --page-size 10
```

`POST /api/internal/listings/snapshots/run` triggers the same cycle. It is internal-only and must be protected by application authentication before production use. Pagination stops when Amazon returns no next token or the configured max-pages safety limit is reached. A failed page stops safely; an individual snapshot failure is isolated and does not abort the other listings.

No scheduler is included yet. Future deployment can call the reusable job from Windows Task Scheduler, cron, or AWS Lambda/EventBridge without changing its collection logic. Amazon access remains read-only.
