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

## Step 10 — AWS Scheduled Snapshot Deployment

Local development retains SQLite. AWS Lambda uses DynamoDB through the same snapshot repository contract: EventBridge Scheduler → Lambda → read-only Amazon SP-API → SnapshotCollector → DynamoDB. Lambda does not use SQLite or durable `/tmp` storage.

Set these Lambda environment variables: `SECRET_ARN`, `SELLER_ID`, `MARKETPLACE_ID`, `STORAGE_BACKEND=dynamodb`, `DYNAMODB_SNAPSHOTS_TABLE`, and `DYNAMODB_RUNS_TABLE`. The referenced Secrets Manager JSON contains only `SP_API_CLIENT_ID`, `SP_API_CLIENT_SECRET`, and `SP_API_REFRESH_TOKEN`. Values are loaded at runtime and never returned or logged.

The snapshot table partition key is `seller_marketplace_asin` (`seller_id#marketplace_id#asin`) with sort key `captured_at`. The run table uses `run_id`. Both store normalized data only. Lambda handler: `lambda_handler.lambda_handler`. EventBridge Scheduler configuration is a manual post-deployment step.

Build a deployment ZIP only; this never uploads or creates AWS resources:

```powershell
.\deploy\build_lambda.ps1
```

## Step 11 — Listing Intelligence Engine

The Listing Intelligence Engine analyzes only seller-scoped historical snapshots through the repository contract, so it works with both local SQLite and DynamoDB storage. `GET /api/listings/{asin}/intelligence?window=30` supports `7`, `30`, `60`, `90`, and `all` windows and returns normalized historical signals only.

Scores are deterministic, bounded 0–100, and are not predictions. Stability starts at 100 and subtracts weighted change frequency, status/title/fulfillment changes, then adds up to 15 duration points. Risk adds points for non-active status, repeated status/title/fulfillment changes, price movement of at least 20%, recent changes, and insufficient history. Opportunity rewards stability, consistently active status, sufficient history, and low operational risk. Confidence is high at 10 snapshots and 30 days; medium at 4 snapshots and 7 days or at least 2 snapshots across 30 days; otherwise it is low.

Risk flags describe historical operational conditions only; opportunity flags do not indicate sales, demand, profit, or a recommended Amazon change. This is historical listing intelligence, not sales prediction.


## Step 12 — Recommendation Layer

Recommendations follow a deterministic chain: repository → Listing Intelligence → Recommendation Service → normalized API response. `GET /api/listings/{asin}/recommendations?window=30` supports the same history windows as intelligence.

Actions include `KEEP_STABLE`, `WAIT_FOR_MORE_DATA`, `REVIEW_TITLE`, `CHECK_LISTING_STATUS`, `REVIEW_PRICE_VOLATILITY`, `REVIEW_FULFILLMENT`, `INVESTIGATE_RECENT_CHANGE`, and `MONITOR_LISTING`. Risk flags map directly to seller-friendly recommendations with low, medium, high, or critical priority. Insufficient history remains low priority; unstable status and multiple high-risk signals raise priority.

Recommendations are deterministic historical guidance only. They do not modify Amazon, predict sales or profit, or replace seller review. A human must review any recommendation before making a change in Seller Central.

## Step 13 — LLM Explanation Layer

The deterministic recommendation engine remains the source of truth. The optional explanation layer only converts its normalized actions into concise seller-facing text. `GET /api/listings/{asin}/explanation?window=30` uses deterministic fallback whenever no provider is configured, a provider fails, or its output fails validation.

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` only in the runtime environment to enable the OpenAI provider. No key is required for the application to work. The provider receives only normalized recommendation data; it never receives Amazon credentials, tokens, headers, raw API payloads, or buyer data.

LLM output must preserve the deterministic overall action, priority, action ordering, and action codes. Invalid output is rejected. The LLM explains recommendations; it does not decide or execute Amazon actions, predict sales/profit, or suggest autonomous writes.

## Step 14 — Consolidated Seller Insights API

`GET /api/listings/{asin}/insights?window=30` combines the latest normalized listing snapshot, windowed history summary, deterministic intelligence, deterministic recommendations, and the validated explanation layer. It reuses existing services and does not duplicate their scoring or action rules.

The response is suitable for a seller dashboard and remains strictly read-only. It excludes listing hashes, credentials, tokens, headers, raw Amazon payloads, and buyer data. Empty, partial, and missing-price history returns safe null/default values. Insights are historical operational context, not sales, profit, or demand prediction.
