# Circular kitchen extension — implementation audit

The attached extension request was reviewed against the existing code and live SQLite schema before edits. The existing application was extended in place. Original numbered specifications and supplied datasets remain unchanged. No packages, provider integration, authentication or external processing service were added.

## Audit and scope

| Area | Before this extension | Delivered |
|---|---|---|
| Forecasts, simulator, rolling backtests, cost optimization | Working | Preserved algorithms and historical training data. New dinner actuals become earlier-only dinner observations. Sparse dinner history still requires manual quantities. |
| CSV import, mass balance, approved plans, offline reports | Working | Preserved. Reuse plans additionally retain fresh/reused provenance; offline evidence explains the transfer. |
| Recovery reviews, approvals, plate-waste block, split receipts | Working | Shared ledger now includes dinner reservations. Unknown-origin batches also share the total recorded-mass pool. Changed evidence invalidates unused reuse approvals. |
| Lunch-to-dinner planning | Missing | Detailed handling logs, deterministic fail-closed checks, same-dish compatibility, dinner demand check/manual fallback, atomic reservation, qualified-manager attestation, approve/reject/release, linked actual outcome. |
| Biogas handoffs | Working; no energy estimate | Editable assumptions, preview, segregation confirmation for estimates, accepted processor gate, immutable receipt assumptions, theoretical gas/electricity/heat and separate unmeasured actual energy. Legacy receipts remain readable without invented estimates. |
| Inventory date alerts | Working; label type unspecified | Per-day staff review, use-by / best-before / unknown distinction, storage and condition eligibility. Original ingredient quantities and source labels retained. |
| Recipe recommendations | Missing | Deterministic raw-ingredient bills for four illustrative hostel dishes; eligible alternatives ranked by near-use-by usage, per-batch usage and procurement shortages. No cooked yield is invented. |
| UI | Working Kitchen Fieldbook | Existing navigation and bright design retained; new recovery, impact and overview sections use semantic forms, live status and contained scrolling tables. |
| Deferred | Optional integrations | Chilled/ambient reuse, dish transformations, measured recipe yields/nutrition, stock consumption/reservations, actual processor operation and measured energy. |

## Safety and accounting boundaries

The supported reuse path is **same-day hot holding of the identical cooked dish**. All five existing handling checks and current batch-manager approval are required. Detailed evidence must include a nonblank kitchen procedure, staff reviewer, protected separate container, continuous-monitoring review, explicit procedure permission for this food, timezone-aware start/end, and ordered distinct temperature readings covering the entire interval.

The demonstration gate uses 63–100 °C, a maximum six-hour holding interval and maximum 60-minute log gaps. The 63 °C hot-holding floor is informed by [FSA guidance](https://www.food.gov.uk/safety-hygiene/cooking-your-food); the upper bound, duration and logging interval are explicitly conservative **demo assumptions**, not a complete HACCP procedure or Indian regulatory compliance rule. Chilled, ambient, missing, unknown and failed evidence is blocked. A qualified manager must explicitly attest qualification and review of the applicable kitchen procedure. Names and qualification attestations are not independently verified; authentication was explicitly excluded. A synthetic example log is available only for synthetic untouched food, and is never loaded silently.

Reuse proposals reserve cooked mass inside the existing recovery batch. Pending, approved and completed reuse quantities reduce handoff availability. Approvals bind a SHA-256 snapshot of the handling evidence. Review/evidence changes or renewed batch approval invalidate unused proposals and release their reservations; completed actual outcomes remain immutable. Batch mass/origin cannot change while reuse is reserved or completed. Rejected proposals release mass. SQLite `BEGIN IMMEDIATE` makes concurrent reservation/handoff checks atomic. Unknown-origin allocations block reuse until classified, and total allocations cannot exceed the record's untouched-plus-plate mass.

An approved dinner plan stores **total food available**, **fresh preparation**, and **reuse** separately. The existing `prepared_kg` actual field means total food at that service when linked to a reuse plan; the form makes this explicit. Backend validation requires total actual food to cover reserved reuse, retains the lunch source label, and permits one actual per plan item. Fresh actual mass is calculated as total minus reuse. Served-food forecasting continues to use consumed plus plate waste, including reused food served at dinner. Reuse is a transfer, not new food or proof of waste prevention. The circular dashboard separately reports gross service-food mass and newly prepared actual mass. It does not add reused food to consumed food or aggregate reuse with projected prevention.

Plate waste is permanently excluded from both human redistribution and dinner reuse. Only explicitly accepting demo processors can receive it. Compost remains supported. Animal feeding and insect-farming routes were not added.

## Biogas calculation

All values are calculated on the backend. Defaults are **illustrative editable scenario inputs**, not fitted or measured processor performance:

| Input | Default | Unit |
|---|---:|---|
| Wet-food biogas yield | 0.10 | m³ biogas / kg wet food |
| Methane fraction | 0.60 | m³ methane / m³ biogas |
| Methane energy assumption | 9.94 | kWh / m³ methane |
| Electricity conversion | 0.35 | fraction of chemical energy |
| Useful heat recovery | 0.45 | fraction of chemical energy |

`biogas = wet kg × yield`; `methane = biogas × methane fraction`; `chemical energy = methane × energy factor`; electricity and heat are each chemical energy times their respective efficiencies. Combined efficiency cannot exceed 1. Volumes assume a common reference basis; temperature/pressure correction, contamination, digestibility, parasitic loads, losses and actual processor data are not measured.

At 8 kg and the defaults: **0.800 m³ gas**, **0.480 m³ methane**, **4.7712 kWh chemical energy**, **1.66992 kWh potential electricity**, **2.14704 kWh potential useful heat**, **3.81696 kWh combined useful potential**. These are alternatives to measured outcomes, not evidence of generation. Every receipt remains simulated; `actual_measured_energy_kwh` is `null`, never fabricated zero or a generated-energy claim. The accepted processor, segregation attestation and exact assumptions are retained on the receipt. Preview does not allocate food. Retry keys cannot silently change receipt assumptions.

[EPA's anaerobic digestion explanation](https://www.epa.gov/agstar/how-does-anaerobic-digestion-work) supports the process distinction and possible uses of biogas; it does **not** establish these demonstration coefficients for this food.

## Ingredient planning

Existing seed date labels were not silently reclassified. Legacy rows have unknown label type and require staff review for the selected planning date. Storage and condition must explicitly pass. Past use-by stock is blocked. Past best-before stock is described as requiring quality review and excluded from this conservative planner, without equating it to a use-by safety expiry. The distinction follows [official food-label guidance](https://www.gov.uk/understanding-food-labelling/best-before-and-use-by-dates).

Recipe bills are illustrative raw kg per 100 portions and scale on the backend. Eligible batches are used in label-date order, with capped usage and explicit shortages. An existing ingredient with no eligible stock excludes that recipe. Missing ingredients require verified procurement. Each suggestion is an alternative scenario, not a simultaneous allocation; viewing it never reserves or consumes inventory. Cooked output is null and no raw-to-cooked conversion is implied. All templates require kitchen review, ingredient/allergen verification and local portion/yield validation.

## Backward-compatible migration and preservation

Startup adds `reuse_plans(id TEXT PRIMARY KEY, payload TEXT NOT NULL)` with `CREATE TABLE IF NOT EXISTS`, plus `meta.schema_version = 2`. Existing JSON-backed tables receive optional fields only when the new workflow is used: batch holding evidence, plan fresh/reuse quantities and state, receipt potential/segregation, and inventory review metadata. Existing tables and rows are not rebuilt or reset. Old request bodies remain valid. Explicit demo reset additionally clears the reuse ledger and restores the original inventory without annotations.

An online SQLite backup was made before edits: `artifacts/pre-circular-20261009-125629.sqlite3`. Preservation verification compared every pre-existing ID and JSON payload against that backup; all were retained. Inventory gained review annotations while all original fields remained identical. All 14 hashed supplied data/specification files remained byte-identical. Detailed results: `artifacts/circular-preservation-result.json`.

## Exact files changed in this extension

Added:

- `backend/app/errors.py` — shared unchanged error contract.
- `backend/app/circular.py` — reuse ledger, handling policy, decisions, biogas calculation, impact and router.
- `backend/app/recipes.py` — inventory eligibility, recipe bills, calculations and router.
- `backend/tests/test_circular.py`, `backend/tests/test_recipes.py` — new domain and regression cases.
- `frontend/src/components/CircularKitchen.tsx`, `frontend/src/components/IngredientRecipes.tsx` — integrated forms and result views.
- `docs/CIRCULAR_KITCHEN_IMPLEMENTATION.md`, `docs/CIRCULAR_KITCHEN_VALIDATION.md` — audit, assumptions and executed verification.

Modified:

- `backend/app/db.py` — additive table and reset coverage.
- `backend/app/schemas.py` — strictly bounded new request models and optional receipt assumptions.
- `backend/app/main.py` — shared allocation checks, review invalidation, actual-use integration, inventory labels and offline reuse evidence; original forecasting functions unchanged.
- `frontend/src/pages/RecoveryPage.tsx`, `frontend/src/pages/ImpactPage.tsx`, `frontend/src/pages/OverviewPage.tsx`, `frontend/src/pages/RecordPage.tsx` — connect new sections and preserve source/fresh/reuse semantics.
- `frontend/src/types.ts`, `frontend/src/styles.css`, `frontend/src/App.tsx` — additive types, responsive styles, overview refresh and built-in judge guide.
- `README.md`, `VALIDATION.md`, `docs/DEMO_WALKTHROUGH.md` — current feature, validation and launch/demo pointers.

Generated local artifacts include the database backup, preservation hashes/results and browser screenshots. `backend/foodwise.sqlite3` retains prior state plus the explicitly synthetic connected browser demonstration. No database reset was performed on the user's database.

Framework references checked for these additions: [FastAPI routers](https://fastapi.tiangolo.com/tutorial/bigger-applications/), [Pydantic validators](https://pydantic.dev/docs/validation/latest/concepts/validators/), and [React effect cleanup](https://react.dev/reference/react/useEffect). No new runtime dependencies were needed.
