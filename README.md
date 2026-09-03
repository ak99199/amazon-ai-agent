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

## Step 15 — Portfolio Insights

`GET /api/portfolio/insights` provides a seller-wide, read-only dashboard summary by reusing the existing per-listing insights service. It supports `window`, `sort` (`risk_desc`, `opportunity_desc`, `recent_change`, `stability_desc`), `priority`, `status`, `confidence`, `changed_recently`, `min_risk_score`, and a bounded `limit` up to 200.

The response contains aggregate portfolio counts/averages and normalized per-ASIN summaries only. No listing hash, credentials, tokens, raw Amazon data, or buyer information is exposed. Portfolio metrics are historical operational context, not a sales or profit prediction.

## Step 16 — Seller Dashboard UI

The lightweight seller dashboard uses FastAPI templates, Jinja2, vanilla JavaScript, and CSS. Visit `/dashboard` for seller-wide portfolio metrics, filters, ranking, and listing links. Visit `/dashboard/listings/{asin}` for the current normalized listing, history summary, intelligence, recommendations, and explanation.

The UI depends on the existing read-only portfolio and listing-insights services. Start it locally with `python -m uvicorn main:app --reload`. It handles unconfigured, empty, missing-title, missing-price, and insufficient-history states safely. It is an MVP dashboard: it provides historical operational context only and never modifies Amazon.

## Step 17A — Dashboard Security

The dashboard uses a single-admin session login. Configure `DASHBOARD_ADMIN_USERNAME`, `DASHBOARD_ADMIN_PASSWORD_HASH` (bcrypt hash only), and `SESSION_SECRET_KEY`; set `SESSION_COOKIE_SECURE=true` for HTTPS production deployments. If any required authentication setting is missing, protected routes fail closed and do not bypass authentication.

Protected paths are `/dashboard`, `/api/listings/*`, `/api/portfolio/*`, and `/api/internal/*`. `/health`, `/login`, and login static assets remain public. Sessions are HttpOnly, SameSite=Lax, bounded to eight hours, and use CSRF tokens for login, logout, and the internal snapshot POST route. Security headers and no-store cache policy apply to authenticated content.

`ENABLE_INTERNAL_SNAPSHOT_ROUTE` defaults to `false`. Enable it only for deliberate, authenticated manual operations; the scheduled Lambda remains the normal production collector. This MVP has one shared administrator and should be replaced by managed identity, user accounts, audit trails, and rate limiting before broader production use.

## Step 17B — Lambda Web Dashboard

The web dashboard uses a separate Lambda Function URL function, distinct from the existing `amazon-sp-api-agent` snapshot Lambda. Browser → Function URL → FastAPI/Mangum → DynamoDB. Handler: `web_lambda_handler.handler`.

Build the web artifact only with `./deploy/build_web_lambda.ps1`; it creates `dist/amazon-ai-agent-web-lambda.zip` and does not upload, deploy, or change infrastructure. The build includes the application, templates, static files, `main.py`, `web_lambda_handler.py`, and runtime dependencies while excluding `.env`, tests, local SQLite data, caches, Git metadata, and existing distribution files.

For production set `STORAGE_BACKEND=dynamodb`, `DYNAMODB_SNAPSHOTS_TABLE`, `DYNAMODB_RUNS_TABLE`, `DASHBOARD_ADMIN_USERNAME`, `DASHBOARD_ADMIN_PASSWORD_HASH`, `SESSION_SECRET_KEY`, `SESSION_COOKIE_SECURE=true`, and `ENABLE_INTERNAL_SNAPSHOT_ROUTE=false`. Function URL HTTPS supports Secure session cookies and redirects.

The web Lambda needs DynamoDB read permissions for dashboard reads: `dynamodb:GetItem`, `dynamodb:Query`, and `dynamodb:Scan` scoped to the snapshot table. It does not run scheduled collection; preserve the existing snapshot Lambda and EventBridge role separately. Add IAM permissions manually after review.

## Step 18A — Seller Action Center

The protected `/dashboard` page is now a read-only daily Action Center. It prioritizes the existing deterministic listing recommendations in critical, high, medium, then low priority order, with risk score as a deterministic tie-breaker. Each item links to its listing detail page and retains the underlying action code while presenting a seller-friendly label.

The dashboard includes portfolio KPIs, including a deterministic **Needs attention** count for critical and high-priority recommendations. Its filters retain the portfolio priority, status, confidence, sort, and changed-recently controls, and add risk level and needs-attention filtering. The listing table has responsive layout, readable badges, truncated product titles, safe missing-value states, and direct ASIN links.

Listing detail pages now group normalized current listing data, historical intelligence, deterministic recommended actions, an optional clearly-labelled AI explanation, and recent snapshot history. The AI explanation is contextual only: it is not a prediction and never changes an action or makes an Amazon update. All dashboard data remains authenticated, seller-scoped, read-only, and excludes secrets, hashes, raw Amazon payloads, and buyer information. Human review remains required before any Seller Central action.

## Step 18B — Alerts Foundation

The alerts foundation is a deterministic, seller-scoped internal notification layer that can be reused by future Amazon Ads workflows. It evaluates normalized listing intelligence and recommendations only: inactive listings, high risk, high/critical recommendations, recent major changes, fulfillment instability, and important price volatility. An LLM never decides whether an alert exists.

Each alert is stored independently from listing snapshots with a stable dedupe key based on seller, marketplace, ASIN, alert type, and relevant normalized state. Local development uses the existing SQLite database. Production can use a separate DynamoDB table with `seller_marketplace` as partition key and `created_at_alert_id` as sort key, configured through `DYNAMODB_ALERTS_TABLE`. The table is not created automatically.

`GET /api/alerts` supports optional `status` (`new`, `sent`, `dismissed`) and `severity` filters. `POST /api/alerts/{alert_id}/dismiss` changes only the internal alert status and requires the existing authenticated session plus CSRF header. Both routes are read-only with respect to Amazon.

Set `ALERTS_ENABLED=true` and `ALERT_NOTIFICATION_PROVIDER=log` for a safe development notification sink. Optional SNS delivery additionally requires `ALERT_NOTIFICATION_PROVIDER=sns` and `ALERT_SNS_TOPIC_ARN`; only normalized alert title and message are sent. No topic, subscription, or AWS permission is created by this project. Future production flow: snapshot Lambda → deterministic alert evaluation → DynamoDB alerts table → optional SNS → seller-managed email/SMS subscription. Human review is always required.

## Step 18B.1 — Snapshot Alert Evaluation

The existing scheduled snapshot Lambda now evaluates alerts only after a successful read-only collection run. The integration is in `run_listing_snapshot_job`: it selects seller-scoped listings changed in that run, reuses `ListingIntelligenceService` and `ListingRecommendationService`, then passes their normalized output to `AlertService`. It does not duplicate scoring or recommendation rules and does not make any Amazon write.

Set `ALERTS_ENABLED=true` on the snapshot Lambda to activate evaluation. Set `DYNAMODB_ALERTS_TABLE` to a separately provisioned table using `seller_marketplace` as its partition key and `created_at_alert_id` as its sort key. `ALERT_NOTIFICATION_PROVIDER` is optional; without it, alerts are stored but no notification is sent. Configure `log` for safe logging, or `sns` with `ALERT_SNS_TOPIC_ARN` for optional SNS delivery. The web Lambda only reads alerts and never evaluates or sends them.

Alert evaluation and notification failures are isolated: they log only the exception type and leave a successful snapshot collection successful. The snapshot Lambda requires alerts-table `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:Query`, and `dynamodb:Scan` as applicable to the repository; SNS requires `sns:Publish` only when enabled. The web Lambda needs only read permissions (`dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:Scan`) for the alerts table. IAM resources and policies are not created or changed automatically.

## Step 19A.1 — Amazon Ads API Client Foundation

Amazon Ads API approval is pending. This project now contains an isolated, read-only client foundation in `app/amazon_ads`; it does not reuse SP-API credentials or alter the existing SP-API, snapshot Lambda, or dashboard flows.

Configure only when Ads access is approved: `AMAZON_ADS_CLIENT_ID`, `AMAZON_ADS_CLIENT_SECRET`, `AMAZON_ADS_REFRESH_TOKEN`, `AMAZON_ADS_PROFILE_ID`, and optional `AMAZON_ADS_REGION` (`NA`, `EU`, or `FE`; defaults to `FE`). Far East resolves to `https://advertising-api-fe.amazon.com`, supporting India profile discovery.

The intended authorization path is: LwA Ads client → advertiser authorization → refresh token → short-lived access token → profile discovery → explicitly selected India profile → read campaigns/reporting. Tokens are kept in memory only. The client exposes GET and an explicitly read/report-oriented POST helper; it has no PUT, PATCH, DELETE, bid, budget, keyword, or campaign mutation APIs. Profile discovery calls `/v2/profiles` without a profile-scope header; scoped read/report calls include the configured profile header. No live Ads API call is made by this foundation.

## Step 19A.2 — Ads Historical Data + Reporting Foundation

Amazon Ads API approval remains pending. This read-only foundation prepares the flow: Amazon Ads reports → normalized Ads performance rows → historical SQLite repository → deterministic metrics engine → future Ads recommendation engine. All current tests use mocked report rows; no live Ads request or campaign mutation is performed.

`AdsPerformanceDaily` stores seller, marketplace, profile, date, Sponsored Products dimensions (campaign, ad group, keyword/target, and search term when supplied), currency, and decimal-safe performance metrics. The separate `ads_performance_daily` SQLite table is isolated from listing snapshots. A deterministic dimensional hash gives reprocessed report rows safe upsert behavior. Profile/date, campaign/date, keyword/date, and search-term/date indexes support historical querying.

The reporting foundation supports future Sponsored Products campaign, ad group, keyword, targeting, and search-term report definitions. It normalizes mock report rows with missing dimensions, zero values, numeric strings, or numeric values, and rejects invalid monetary metrics safely. `AdsMetricsService` calculates CTR, CPC, CVR, ACOS, and ROAS with Decimal arithmetic and derives aggregate metrics from totals rather than averages. Historical queries are seller/marketplace/profile scoped and support 7, 14, 30, 60, 90 day or custom bounded date ranges.

## Step 19A.3 — Ads Ingestion Orchestration

Amazon Ads approval is still pending. The ingestion pipeline is source-injected and tested only with mocks: Ads API read services → campaigns / keywords / targets → search-term report rows → normalized historical rows → `AdsPerformanceRepository` → `ads_ingestion_runs` diagnostics. No live Ads API call, campaign mutation, bid change, budget change, or keyword/targeting write is exposed.

Sponsored Products campaign and keyword/target services are read-only, profile-scoped normalizers. `AdsIngestionService` runs a bounded cycle using injected sources, validates inclusive date ranges up to 90 days, limits campaign/keyword pages and report rows, and reuses daily-row upserts for idempotent report replays. The separate `ads_ingestion_runs` SQLite table stores only seller/marketplace/profile-scoped counters and sanitized error summaries; it never stores raw report payloads, credentials, tokens, or headers. Individual malformed report rows are isolated and counted while valid rows continue; source-level failures produce a sanitized failed run record.

## Step 19A.4 — Ads Readiness & Diagnostics

The authenticated Ads status flow is: Ads approval/config state → readiness service → historical Ads repository → ingestion-run diagnostics → authenticated API → Seller Action Center. Current statuses are `approval_pending`, `configuration_incomplete`, `profile_not_selected`, `no_ads_data`, and `ready`. Approval defaults to pending and is controlled only by `AMAZON_ADS_APPROVAL_STATUS`; no live Amazon approval check is made.

`GET /api/ads/readiness`, `GET /api/ads/diagnostics`, and `GET /api/ads/ingestion-runs` are authenticated, read-only visibility endpoints. They return only booleans, counts, timestamps, and normalized run fields—never Ads credentials, access/refresh tokens, headers, raw payloads, or errors. The Seller Action Center shows a safe Amazon Ads Readiness panel and degrades to an unavailable message if diagnostics fail. Amazon Ads approval remains pending; this step makes no live Ads call and adds no mutation operation.

## Step 19A.5 — Deterministic Ads Recommendation Engine

Historical normalized Ads rows flow through `AdsMetricsService`, `AdsSignalService`, and `AdsRecommendationService` into the authenticated `GET /api/ads/recommendations` endpoint and the Seller Action Center. The engine is recommendation-only: it has no live Amazon Ads calls and no endpoints or code paths that change bids, budgets, campaigns, keywords, targeting, or negative keywords.

Supported analysis windows are 7, 14, 30, 60, and 90 days. Recommendations are seller-, marketplace-, and Ads-profile-scoped and may analyze campaign, keyword, or search-term rows. All rates (CTR, CPC, CVR, ACOS, ROAS) are derived once from aggregated Decimal-safe totals rather than averaged from daily rates. Low confidence produces `INSUFFICIENT_DATA`; stronger rules require deterministic history/sample thresholds.

The centralized environment thresholds are optional: `AMAZON_ADS_TARGET_ACOS_PERCENT` (default `30`), `AMAZON_ADS_MIN_IMPRESSIONS_FOR_CTR` (`100`), `AMAZON_ADS_LOW_CTR_PERCENT` (`0.30`), `AMAZON_ADS_MIN_CLICKS_FOR_CVR` (`10`), `AMAZON_ADS_LOW_CVR_PERCENT` (`2`), `AMAZON_ADS_HIGH_CPC_AMOUNT` (`50`), and `AMAZON_ADS_WASTED_SPEND_THRESHOLD` (`500`). Invalid configured values fail safely when the recommendation service is invoked; no malformed threshold is silently accepted.

Implemented codes include `INSUFFICIENT_DATA`, `KEEP_STABLE`, `HIGH_ACOS`, `LOW_CTR`, `LOW_CVR`, `HIGH_CPC`, `WASTED_SPEND`, `PROFITABLE_SEARCH_TERM`, `KEYWORD_HARVEST_CANDIDATE`, `NEGATIVE_KEYWORD_CANDIDATE`, `BID_DECREASE_CANDIDATE`, and `BID_INCREASE_CANDIDATE`. The engine never emits both bid directions for one scope/window; wasted-spend and high-ACOS signals take negative precedence. `BUDGET_PRESSURE` remains defined but unused because historical budget utilization is not yet stored.

`GET /api/ads/recommendations?window=30&scope_type=search_term&limit=50` is authenticated and read-only. It returns normalized recommendations and aggregate metric snapshots only—never credentials, tokens, headers, raw Ads payloads, or buyer information. The dashboard shows up to five entries and degrades safely for pending approval, missing configuration/profile, no historical Ads data, or recommendation-service failure. Amazon Ads approval remains pending; all test data is local or mocked and every recommendation requires human review.

## Step 19A.6 — Ads Action Center + Human Approval Workflow

The internal Action Center extends current deterministic Ads recommendations with a seller decision: `pending`, `approved`, `rejected`, or `dismissed`. A recommendation without a persisted decision is shown as virtual `pending`; merely viewing the dashboard does not create a database row. `approved` means **approved for future execution / accepted recommendation only**. It does not apply, execute, or send any Amazon Ads change.

Flow: historical Ads data → deterministic recommendations → Ads Action Center → human decision → internal SQLite decision record and immutable audit event. The flow deliberately stops there. A future, separately designed phase could introduce an execution safety check and controlled Amazon Ads change, but that capability is not implemented.

SQLite adds `ads_recommendation_decisions`, scoped by seller, marketplace, profile, and stable recommendation ID, with one current row per scope/ID. `ads_recommendation_decision_events` records each real review change, including old/new status, sanitized note, source, and UTC timestamp. Repeating the same status and note does not duplicate either record or audit event. Historical decisions are retained even when a recommendation is no longer current.

Authenticated routes are `GET /api/ads/actions?window=30&status=pending&priority=high&limit=50` and `POST /api/ads/actions/{recommendation_id}/decision`. The POST requires the existing session and CSRF header and accepts only `approved`, `rejected`, or `dismissed`, plus an optional trimmed plain-text review note capped at 1,000 characters. It updates only internal review state and returns no credentials, tokens, headers, raw payloads, or Amazon execution data.

The Seller Dashboard shows action counts, current recommendation details, review-note input, and Approve/Reject/Dismiss controls. It explicitly states that no Amazon Ads changes are executed. The panel fails independently without affecting listing Action Center, alert, or Ads readiness panels. Amazon Ads approval remains pending and this project still has no Ads mutation or live network path in this workflow.

## Step 19A.7 — Controlled Ads Execution Safety Layer (Dry-Run Only)

The controlled execution safety layer stops at a persisted simulation. Its flow is: historical Ads data → deterministic recommendation → human review → approved internal decision → safety validation → dry-run execution plan → **STOP**. Step 19A.7 has no Amazon Ads mutation, executor, write client, or execute/apply/push endpoint.

`AdsExecutionPlanService` resolves both the current recommendation and its stored server-side decision. It requires `approved`, validates seller/marketplace/profile scope, rejects stale or unsupported recommendations, applies dry-run/configuration checks, and records a deterministic plan hash. The plan never invents a bid or budget amount: `current_value` and `proposed_value` remain null while direction-only plans such as `BID_DIRECTION_REVIEW` are used.

SQLite adds `ads_execution_plans` and `ads_execution_events`. One scope-bound `plan_hash` gives repeated dry-run requests idempotent behavior, while only a changed plan state appends a new audit event. Every plan stores `dry_run=true`; this cannot be changed by request input.

Safety configuration is centralized: `AMAZON_ADS_EXECUTION_ENABLED=false`, `AMAZON_ADS_DRY_RUN_ONLY=true`, max bid/budget increase/decrease percentages (all default `20`), `AMAZON_ADS_MAX_SINGLE_ACTION_AMOUNT=0`, and `AMAZON_ADS_MAX_ACTIONS_PER_RUN=1`. Invalid values fail safely. Even if an environment accidentally enables execution, Step 19A.7 never sends a live write; a false dry-run-only setting blocks planning.

Authenticated endpoints are `GET /api/ads/execution-plans` and `POST /api/ads/actions/{recommendation_id}/dry-run`. The POST requires the existing CSRF protection and creates internal plan metadata only. The dashboard labels this as “Simulation only — no Amazon Ads changes are sent.” Live Ads API writes are a future-only capability and are not implemented.

## Step 19A.8 — Amazon Ads Live Read Wiring Foundation

The live-read boundary prepares the approved future flow: LwA credentials → Ads authentication → profile discovery → explicitly selected profile → read-only campaign/ad group/keyword/target reads → bounded report request/poll/download → existing normalization and historical storage. It reuses the existing LwA and read-only client abstractions; access tokens remain runtime-only and are never persisted or returned.

`AMAZON_ADS_LIVE_READ_ENABLED=false` and `AMAZON_ADS_USE_MOCK_DATA=true` are the safe defaults. When live reads are disabled or mock mode is active, no live Amazon request is made. If enabled, the service still blocks before any request for pending approval, incomplete credentials, or missing explicit `AMAZON_ADS_PROFILE_ID`; it never auto-selects a discovered profile.

`GET /api/ads/live-read/status` and `GET /api/ads/live-read/profiles` are authenticated, read-only visibility routes. The profile route returns a safe blocked state without requesting Amazon until live-read prerequisites are ready. Modes include `disabled`, `mock`, `blocked_approval`, `blocked_config`, `blocked_profile`, and `ready_live`; sanitized auth/rate-limit/remote failures remain distinct from tokens and raw error payloads.

Sponsored Products adapters isolate endpoint versions and bounded pagination for campaigns, ad groups, keywords, and targets. The report transport isolates read/report creation, bounded polling, and normalized row download with injectable transport/sleeper. All tests use fakes; Amazon Ads approval remains pending. No Ads entity mutation, automatic scheduler, AWS change, or live-write/execution endpoint is implemented.

## Step 19A.9 — Live Ads Ingestion Activation Gate + Manual Sync

Manual Ads synchronization is now guarded by deterministic server-side readiness checks: feature mode, approval, configuration, explicit profile selection, bounded dates, active-run protection, and cooldown. The flow is: readiness → sync gate → manual sync request → injected mock/live read services → existing Ads ingestion/storage → scoped sync diagnostics. There is no scheduler, EventBridge rule, background loop, Lambda trigger, or automatic polling added by this step.

`AMAZON_ADS_USE_MOCK_DATA=true` permits local/mock sync by default. Live mode requires `AMAZON_ADS_USE_MOCK_DATA=false`, `AMAZON_ADS_LIVE_READ_ENABLED=true`, approved access, complete Ads configuration, and an explicit profile. A failed gate returns before any runner or Amazon request can occur. `AMAZON_ADS_MANUAL_SYNC_COOLDOWN_SECONDS` defaults to `60`; active `starting`/`running` records younger than 30 minutes block overlapping requests.

`POST /api/ads/sync` is authenticated and CSRF protected and accepts only a bounded server-side date range or `window_days` (1–90). It never accepts credentials or profile secrets from the request. `GET /api/ads/sync/status` and `GET /api/ads/sync-runs` provide safe gate/run diagnostics. Sync runs are persisted in `ads_sync_runs`, scoped by seller, marketplace, and profile, with sanitized counters and errors only.

The dashboard exposes a compact manual Sync panel. Its button is disabled whenever no safe mode is allowed and states plainly that sync only reads Amazon Ads data; it never changes campaigns, bids, budgets, keywords, or targeting. All Amazon Ads entity operations remain read-only.

## Step 19A.10 — Ads Sync Observability + Run History

Manual sync runs now flow through the scoped sync repository into deterministic health classification and authenticated visibility APIs. Health states include `healthy`, `idle`, `running`, `degraded`, `failing`, `blocked`, `stale`, and `never_synced`. The observability service reports only safe run metadata, row counts, error codes, time-window totals, success rate, cooldown, blocked reason, and stale-run state.

`GET /api/ads/sync/observability` and `GET /api/ads/sync/history?limit=20` are authenticated read-only routes. The Seller Action Center shows Sync Health plus recent runs, safe errors, and counts. Retry remains the existing CSRF-protected manual `POST /api/ads/sync` route; no bypass, forced unlock, scheduler, AWS change, or Ads write capability is introduced.

## Step 19A.11 — Ads Performance Intelligence Dashboard

The authenticated `GET /api/ads/intelligence?window=30&limit=10` endpoint combines normalized, seller/profile-scoped historical Ads records with deterministic recommendations, human-review decisions, and sync health. It supports 7, 14, 30, 60, and 90 day windows.

The response aggregates base metrics first and then derives CTR, CPC, CVR, ACOS, and ROAS with Decimal-safe calculations. It includes chronological observed-day trend points (days without data are omitted consistently), a previous-period comparison with safe unavailable values for zero denominators, deterministic campaign/keyword/search-term rankings, recommendation counts, and review-outcome counts.

The Seller Dashboard adds an Amazon Ads Intelligence panel with KPI cards, a window selector, observed-day trend table, ranked performance summaries, and the explicit notice that approved recommendations are only approved for possible future execution. This phase is analytics only: it makes no Amazon Ads writes, has no scheduler, and never auto-executes an approved recommendation.

## Step 19A.12 — Recommendation Effectiveness Tracking

Decision effectiveness uses the existing, seller/marketplace/profile-scoped human decision records. The authenticated `GET /api/ads/effectiveness?window=30` endpoint reports current-state approval, rejection, dismissal, and pending analytics. `GET /api/ads/effectiveness/feedback` provides reviewed-only, structured internal feedback records without raw review-note text.

New decisions capture one immutable, safe deterministic recommendation snapshot at review time. Older decisions correctly report unavailable snapshot context rather than reconstructing historical metrics from current data. The dashboard labels recurring approval/rejection patterns as human-review patterns only.

Feedback analytics do not automatically change recommendation rules or Amazon Ads settings. There is no autonomous learning, threshold tuning, scheduler, Amazon Ads write, or execution in this phase.

## Step 19A.13 — Offline Threshold Evaluation

Rule-tuning proposals are generated only from reviewed, safe historical feedback snapshots. The bounded offline evaluator uses the existing active/default thresholds as an immutable baseline and never wires proposed values into the recommendation engine. `GET /api/ads/rule-tuning` generates review-only candidates for 30/60/90-day windows; `GET /api/ads/rule-tuning/proposals` lists persisted proposals.

No automatic threshold changes, active-rule switch, Amazon Ads write, execution, or scheduler is implemented.

## Step 19A.14 — Rule Version Activation Safety + Rollback

The controlled internal flow is: Offline Rule Proposal → Human Proposal Approval → Proposed Rule Version → Activation Safety Checks → Explicit Human Activation → Active Recommendation Thresholds. Approval for a future rule version does not activate it; activation is a separate authenticated, CSRF-protected action with explicit confirmation and optimistic concurrency.

Rollback follows: Active Version → Explicit Human Rollback → Previous Valid Version from activation history → Recommendation Engine Uses Restored Thresholds. Activation and rollback are atomic, audited, seller/marketplace/profile scoped, and never rewrite threshold snapshots or historical decisions. The resolver is read-only: an active persisted version supplies deterministic recommendation thresholds, while no persisted active version preserves the existing environment/default configuration.

No Amazon Ads entity write occurs in Step 19A.14. Rule activation and rollback change internal recommendation thresholds only; they do not modify campaigns, bids, budgets, keywords, or targeting.

## Step 19A.15A — Production Ads Readiness + Manual Live Read Smoke Test

The production transition is explicitly gated: Approval → Credential Configuration → Region → Explicit Profile Selection → Live-Read Flag with Mock Mode Off → Explicit Manual Smoke Test → Safe Read Result. Approval defaults to pending, profiles are never auto-selected, and every blocked state returns before OAuth or Amazon Ads network dependencies are constructed.

The authenticated, CSRF-protected `POST /api/ads/live-smoke-test` accepts only `confirm_live_read`. When every production gate passes, it refreshes authentication through the existing LwA boundary and performs one bounded, profile-scoped Sponsored Products campaign read. Results contain only safe status, timing, region, presence indicators, stage, safe HTTP status, and bounded record counts; tokens, credentials, headers, and raw remote payloads are never returned or persisted.

Step 19A.15A adds no Amazon Ads write, scheduled sync, autonomous activation, AWS change, or deployment.

## Step 19A.15B.1 — Profile + Campaign Live Read Validation

The explicit validation flow is: Production Readiness → Manual Confirmation → Profile Discovery and Configured-ID Match → One Bounded Sponsored Products Campaign GET → Row-Isolated Structural Validation → Safe Diagnostics. The configured advertiser profile remains authoritative and is never replaced or auto-selected from discovered profiles.

Campaign validation requests one page of at most ten records, reuses existing profile-scoped GET and campaign normalization boundaries, and reports only safe profile metadata plus received, valid, invalid, and duplicate counts. Malformed rows are isolated and raw Amazon payloads are never returned or persisted.

This step is read-only. It adds no campaign mutation, keyword or target read, report API call, ingestion, scheduler, AWS change, or deployment.

## Step 19A.15B.2 — Keyword + Target + Relationship Live Validation

The bounded read-only flow is: Production Readiness → Configured Profile Match → Campaign → Ad Group → Keyword / Target → Relationship Validation → Safe Diagnostic Summary. Each entity uses one profile-scoped GET with limits of 10 campaigns, 20 ad groups, 25 keywords, and 25 targets.

Rows are normalized and validated independently for identifiers, states, match types, finite non-negative bids, and safe target-expression structure. Relationships are valid when a bounded parent is present and consistent, invalid only when known child and parent campaign references contradict, and unresolved when a parent may simply fall outside the bounded page. Missing bounded parents are never labeled as proven orphans.

This step is read-only and non-persistent. It performs no Ads mutation, reporting job, historical ingestion, search-term validation, scheduler, AWS change, or deployment.

## Step 19A.15C.1 — Historical Report Lifecycle Validation

The explicit manual flow is: Production Readiness → Explicit Confirmation → Create One Sponsored Products Campaign Historical Report → Bounded Polling → Terminal Lifecycle Result. The server selects the previous two completed UTC days and permits at most five status checks.

The only POST is creation of a read-only Amazon Ads reporting job; it is not an advertiser mutation. This validation does not download or parse report content, expose signed URLs, persist report jobs or performance rows, create sync runs, schedule work, or modify campaigns, bids, budgets, keywords, or targeting.

## Step 19A.15C.2 — Historical Report Download Validation

The bounded manual flow extends the same lifecycle: Readiness → Confirmation → Create One Report → Poll → Download Once → GZIP Decode → JSON Parse → Validate at Most 100 Rows → Safe Summary. The signed download is limited to 1 MiB compressed and 5 MiB decompressed; oversized or malformed content is rejected in memory.

Campaign DAILY rows require the requested date, campaign ID, and numeric metric columns. Metrics must be finite and non-negative, count metrics must be integral, dates must fall within the requested two-day window, and duplicate report grain is evaluated as date plus campaign ID. Malformed rows are isolated, and reports beyond 100 rows are safely marked truncated.

This validation performs no persistence, sync-run creation, scheduling, recommendation side effects, advertiser mutations, AWS changes, or deployment. Signed locations, raw bytes, parsed rows, and credentials are never returned.

## Step 19A.15C.3.1 — Controlled Historical Report Persistence

The internal flow is: Readiness → Explicit Confirmation → One Historical Report → Download and Fully Validate → Existing Ads Historical Repository → Transactional Idempotent Upsert. Only `success` or `valid_empty` campaign DAILY results may reach the repository; partial or failed reports perform zero performance-row writes.

Rows use authoritative server-side seller, marketplace, and profile scope. The existing logical grain remains seller + marketplace + profile + date + Sponsored Products + campaign dimension, so replay is idempotent and corrected metrics update the existing row. Persistence is local only: there is no public endpoint yet, sync-run creation, scheduler, automatic recommendation processing, advertiser mutation, AWS change, or deployment.

## Step 19A.15C.3.2.1 — Manual Historical Sync Orchestration

The controlled flow is: Authentication → CSRF → Explicit Confirmation → Production Readiness → Scope-Level Concurrency → Successful-Run Cooldown → Sync Run → Historical Report Persistence → Terminal Run Status. `POST /api/ads/manual-historical-sync` accepts only `confirm_live_read`; all seller, marketplace, profile, dates, region, and report configuration remain server-controlled.

Historical attempts reuse `ads_sync_runs` with mode `historical_campaign_report`. Start is atomically rejected when a same-scope Ads sync is active, and the existing configurable manual-sync cooldown is anchored only to the latest successful terminal run. `GET /api/ads/historical-sync-runs` returns bounded, latest-first, scope-isolated history.

This workflow is manual only. It creates no scheduler, background worker, force/bypass option, automatic recommendation work, advertiser mutation, AWS resource, or deployment. Amazon activity remains limited to authentication and report create/status/download operations; only fully validated local performance rows are persisted.

## Step 19A.15C.3.2.2 — Manual Historical Sync Dashboard + Observability

The dashboard flow is: Production Readiness → Historical Sync Health → Explicit Browser Confirmation → Manual Historical Sync → Safe Result → Refreshed Health and Run History. The button sends only `{ "confirm_live_read": true }`, is disabled during execution and whenever readiness, concurrency, or cooldown blocks work, and offers no force or bypass control. Backend gates remain authoritative.

Historical health and history are read-only database views and make zero Amazon requests. Health distinguishes no-sync, running, cooldown, healthy, stale, degraded, and failed states; freshness uses the latest stored campaign report date and treats yesterday's completed reporting day as current. `AMAZON_ADS_HISTORICAL_SYNC_STALE_AFTER_HOURS` is optional and defaults to 72 hours.

The workflow remains manual-only with no scheduler, background worker, AWS change, automatic recommendation action, raw report display, signed URL exposure, or Amazon advertiser mutation.

## Step 19A.16.1 — Scheduled Production Historical Sync Foundation

The trusted callable flow is: Scheduled Sync Enabled? → Production Readiness → Same-Scope Concurrency → Cadence Due? → Existing Historical Sync Execution and Persistence → Existing Run History. `app.jobs.ads_historical_sync_job.run_scheduled_ads_historical_sync()` performs one bounded attempt when explicitly invoked; it is never called on import or application startup.

Scheduled execution is disabled by default with `AMAZON_ADS_SCHEDULED_SYNC_ENABLED=false`. `AMAZON_ADS_SCHEDULED_SYNC_INTERVAL_HOURS` defaults to 24 and is bounded to 1–168 hours. Cadence is anchored only to the latest successful run whose trigger source is `scheduled`, so manual runs retain their existing confirmation/cooldown behavior without permanently shifting scheduled cadence.

The existing `ads_sync_runs` table now has a backward-compatible `trigger_source` value (`manual` for existing/manual rows and `scheduled` for trusted job runs). Manual and scheduled execution share the same atomic run lifecycle, persistence pipeline, same-scope concurrency protection, and idempotent performance grain.

No scheduler, EventBridge resource, cron entry, startup hook, background loop, Lambda/IAM change, AWS deployment, public scheduled-execution endpoint, advertiser mutation, force option, or retry loop is included. Amazon access remains limited to the existing read/report pipeline.
## Step 19A.16.2 — Scheduled pipeline observability and stale-run recovery

Trusted scheduled invocation now performs stale-run reconciliation before concurrency and cadence checks, then uses the existing historical execution lifecycle. The authenticated manual POST reuses that reconciliation primitive after confirmation and readiness; ordinary health/dashboard GETs never recover runs. `AMAZON_ADS_SYNC_STALE_RUN_AFTER_HOURS` is optional, defaults conservatively to 6 hours, and safely falls back for invalid values. Scheduled health is read-only: it reports scheduled attempts, success/failure streak, next due time, overdue state, readiness, and stale activity without Amazon calls or database recovery. Only trusted execution can atomically transition a same-scope stale `running` run to `failed`. Scheduled sync remains disabled by default; no scheduler, automatic retry loop, AWS resource, or advertiser mutation is added.
## Step 19A.16.3 — Scheduled Lambda runtime preparation

The build-ready handler is `ads_scheduler_lambda_handler.handler`. Build its Linux x86_64 / CPython 3.14 ZIP with `./deploy/build_ads_scheduler_lambda.ps1`; the output is `dist/amazon-ai-agent-ads-scheduler-lambda.zip`. The script only builds an artifact and does not create or update AWS resources.

`AMAZON_ADS_STORAGE_BACKEND=sqlite` is supported for local development. Scheduled Lambda execution intentionally rejects SQLite because Lambda-local storage is not durable. `AMAZON_ADS_STORAGE_BACKEND=dynamodb` also remains blocked until Step 19A.16.4 implements dedicated persistent Ads tables and an Ads adapter; it never falls back to listing snapshot tables or local SQLite. Scheduled synchronization remains disabled by default, and this runtime performs no advertiser mutations.
## Step 19A.16.4 — Persistent DynamoDB Ads historical storage

Set `AMAZON_ADS_STORAGE_BACKEND=dynamodb`, `AMAZON_ADS_DYNAMODB_PERFORMANCE_TABLE=<table name>`, and `AMAZON_ADS_DYNAMODB_SYNC_RUNS_TABLE=<table name>` only after dedicated Ads resources exist. The performance table uses String keys `scope_key` (partition) and `performance_key` (sort). The sync table uses String keys `scope_key` (partition) and `run_key` (sort); no GSI is required for the current historical pipeline.

Validated performance batches use transactional, idempotent logical-grain puts. `LOCK` owns same-scope concurrency, `RUN#...` items retain attempt history, and `SUMMARY#...` items provide deterministic latest success/failure lookup. Normal and stale terminalization conditionally update the run, matching lock, and summaries in one transaction. Local SQLite remains supported. This code does not create tables, IAM permissions, Lambda resources, or EventBridge schedules; those deployment prerequisites remain for Step 19A.16.5. Scheduling remains disabled by default and no advertiser mutations are added.
## Step 19A.16.5A — Secure Amazon Ads Lambda credentials

The scheduled Ads Lambda loads production credentials from a dedicated AWS Secrets Manager secret referenced by the non-secret `AMAZON_ADS_SECRET_ARN` environment variable. Its JSON shape is:

```json
{
  "AMAZON_ADS_CLIENT_ID": "...",
  "AMAZON_ADS_CLIENT_SECRET": "...",
  "AMAZON_ADS_REFRESH_TOKEN": "..."
}
```

Secret values are validated and passed directly through an `AdsSettings` instance; they are never copied into process environment variables or returned by the handler. `AMAZON_ADS_PROFILE_ID`, `AMAZON_ADS_REGION`, seller and marketplace IDs, dedicated Ads DynamoDB table names, approval state, and feature/schedule flags remain non-secret runtime configuration. Actual secret, table, IAM, Lambda, and scheduler creation is deferred to Step 19A.16.5B. Keep `AMAZON_ADS_SCHEDULED_SYNC_ENABLED=false` until that infrastructure and production readiness are validated. Existing Ads behavior remains read/report-only with no advertiser mutations.
## Step 19A.17A — Controlled Ads write gateway foundation

The controlled flow is: historical data → deterministic recommendation → human approval → persisted dry-run execution plan → write preflight → **STOP**. `AMAZON_ADS_WRITE_ENABLED` defaults to `false`, and `AMAZON_ADS_WRITE_DRY_RUN_ONLY` defaults to `true`; both are independent from read and execution-plan settings and malformed values fail closed.

## Step 19A.17B — Controlled Exact-Value Proposal Foundation

The controlled flow is: recommendation → human approval → dry-run plan → trusted current value → bounded exact-value proposal → write preflight → **STOP**. Bid proposals use `Decimal` and deterministic two-decimal, `ROUND_HALF_UP` quantization. `AMAZON_ADS_BID_PROPOSAL_PERCENT` defaults to `0`, which disables proposals, and must remain within the existing direction-specific percentage cap and single-action amount cap.

Amazon Ads approval remains pending, no live current-value provider exists, and no advertiser mutation occurs. Exact values cannot come from client requests; only an injected trusted server-side provider can supply the current value.

## Step 19A.17C — Controlled Write Intent + Audit Ledger

The controlled flow is: recommendation → human approval → dry-run plan → trusted current value → exact-value proposal → write preflight → immutable write intent → audit ledger → **STOP**. Prepared intents and their audit events are seller, marketplace, and profile scoped and use a deterministic idempotency key, so identical preparation cannot create duplicates.

Amazon Ads API approval remains pending and no advertiser mutation transport exists. Write intents are internal preparation only, numeric values cannot be edited by the client, and no Amazon Ads change is sent.

## Step 19A.17D — Write Intent Lifecycle Safety

A prepared write intent undergoes authoritative revalidation and either remains `prepared` or becomes `superseded`; explicit internal cancellation changes `prepared` to `cancelled`. Each terminal transition creates one deterministic audit event and then **STOP**. Stale or cancelled intents cannot be resurrected.

Amazon Ads approval remains pending, no live current-value provider exists, and no advertiser mutation is sent. Clients cannot edit numeric, action, direction, or scope values.

## Step 19A.17E — Trusted Advertiser Target Resolution

The safe flow is: prepared write intent → authoritative lifecycle revalidation → trusted advertiser entity resolution → **STOP**. Only unambiguous keyword-scope `BID_DIRECTION_REVIEW` intents may resolve to metadata for `SP_KEYWORD_BID`.

Amazon Ads approval remains pending, no live target resolver or mutation transport exists, and no Amazon Ads change is sent. Campaign-level bid reviews are never reinterpreted as keyword bids, campaign budgets, ad-group defaults, or placement adjustments; clients cannot provide scope, entity, action, direction, or numeric values.

## Step 19A.17F — Sealed Write Command Foundation

The safe flow is: write intent → authoritative lifecycle revalidation → trusted target resolution → sealed immutable write command → **STOP**. Sealed commands contain internal metadata only; there is no Amazon request payload or advertiser mutation transport.

All command fields are immutable. Bid values use canonical `Decimal` text, so equivalent forms such as `1.0`, `1.00`, and `1.000` hash identically. Full SHA-256 command hashes and derived IDs make repeated preparation deterministic and idempotent. Amazon Ads approval remains pending and no live providers are introduced.

## Step 19A.17G — Persistent Ads Control-Plane Repository Foundation

Local development defaults `AMAZON_ADS_CONTROL_PLANE_BACKEND` to `sqlite`. Future production may select `dynamodb`, which requires a dedicated `AMAZON_ADS_DYNAMODB_CONTROL_PLANE_TABLE`; missing or unknown configuration fails closed without SQLite fallback.

Historical Ads storage owns performance and sync history. Control-plane storage owns human decisions, plans, rules, write intents, sealed commands, and their audit events. This step creates no AWS table or IAM resource, performs no deployment or live Amazon API call, and enables no advertiser mutation.

Write preflight performs internal, server-scoped validation only. Current plans intentionally contain no exact mutation values, so bid-direction and keyword review plans stop at `exact_value_required`. No Amazon Ads advertiser mutation transport, execute/apply/push operation, campaign update, bid or budget change, keyword mutation, or targeting mutation is implemented. Amazon Ads API approval remains pending, and no Amazon Ads change is sent.
