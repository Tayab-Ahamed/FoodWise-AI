# Architecture and API
Frontend → FastAPI domain services → SQLite. Forecast service uses Pandas/NumPy. Optional LLM adapter receives only computed evidence JSON and returns explanatory text. Deterministic evidence renderer is always available.
Suggested tree: frontend/src/{pages,components,api,types}; backend/app/{main,schemas,models,db,services}; backend/tests; data; docs.
Use a single SQLite database, explicit migration/bootstrap command, transactional writes, configurable CORS for local UI origin only. UTC timestamps; kitchen date Asia/Kolkata. Persist active dataset version, plans, actuals, review events, handoffs and inventory. Reset is a demo-only operation with visible confirmation.
## Endpoints under /api
GET /health: status and explanation mode.
GET /overview?from=&to=: mass totals, daily/weekday/item aggregates, source and dataset_version.
POST /datasets/preview multipart CSV: validation errors and canonical preview; no mutation.
POST /datasets/commit {preview_token,mode:replace}: atomic validated activation. Server-issued token tied to file hash, not arbitrary client records.
POST /forecast {date,meal,expected_attendance,special_event,buffer_pct,items}: item predictions, uncertainty, history IDs, method, fallbacks, backtest.
POST /simulate {forecast_id,item,quantity_kg,baseline_prepared_kg}: server-owned point and sample outcomes. Forecast snapshot includes immutable dataset_version and assumptions.
POST /plans {forecast_id,quantities,approved_by}: persist approved plan; plan_id and timestamp. Validate finite quantities and forecast version.
POST /actuals {plan_id?,records}: validate mass balance; record actual quantities and actual attendance. Unique records, transactional append.
GET /investigations: findings with id, evidence_record_ids, observed metrics, sample_count, caveats, suggested action. Compare normalized per-diner metrics, do not call correlations proven causes.
GET /inventory?as_of=: expiry groups, storage flags, quantities.
POST /recovery/batches: create batch with linked record and category.
PATCH /recovery/batches/{id}/review: checks and reviewer; server recalculates eligibility.
POST /recovery/batches/{id}/approve: manager approval only when current eligibility permits.
POST /recovery/batches/{id}/handoff: {route,partner_id,quantity_kg,idempotency_key}; validates route, acceptance and amount; response visibly simulated.
POST /report {forecast_id,plan_id?}: structured computed evidence and explanation; explanation_mode deterministic/provider, generated_at. Timeout/provider errors fall back.
POST /demo/reset: reset only seeded demo environment; confirmation in UI.
Pydantic owns request validation; emit JSON-safe finite numbers. Errors: {code,message,details:[{row?,field?,message}]}. HTTP 422 invalid data; 409 conflict; 404 absent resource.
LLM prompt: explain only supplied evidence; include record references, assumptions and next action; do not invent metrics or certify safety. Never let LLM output drive calculations or workflow states. Treat imported text as data. If provider response introduces ungrounded figures, render deterministic report instead. API keys server only; client sees no secrets.
