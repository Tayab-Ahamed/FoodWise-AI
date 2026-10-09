# FoodWise AI

A working, local-first kitchen decision loop: **inspect history → forecast served food → simulate preparation → manager approval → log actual food → review recovery → inspect outcomes**.

The original specification, datasets and references are preserved. The practice workspace uses the supplied **270 generated historical records**, not the separate one-row accounting fixture. All calculations, validation, state transitions, allocations and receipts run on the FastAPI backend. The AI prep coach trains locally with NumPy and works without an API key. Groq is the default connected evidence provider. Map tiles, directory refresh, current weather and Groq need a connection when requested; saved directory snapshots and the kitchen workflow remain available offline.

## Recipient network and the AI prep coach

In **Field station**, choose **Find nearby organizations** to discover mapped NGOs, social facilities, food banks, soup kitchens and organic processors within 5–30 km of KNSIT. Pins and straight-line distances come from OpenStreetMap through Overpass, with source links and fetch time. Coverage is incomplete; nearby does not mean that an organization accepts cooked food. Public directory snapshots persist in SQLite. The official Bangalore Food Bank and Robin Hood Army contacts are also available; their exact collection points are not invented.

Save a contact, then use **Recovery → Record recipient acceptance** to record direct staff contact, the specific batch/material/route, capacity, evidence and expiry (within 24 hours). **Record a completed handoff** requires measured source records, actual receiver and receipt reference, segregation, remaining food mass and current manager approval for human recovery. Plate waste is blocked from human redistribution on the backend. Receipts are atomic and idempotent, share the existing allocation ledger with reuse and practice handoffs, and retain recipient/acceptance snapshots. Recorded and simulated dispositions have separate impact totals. The software does not contact recipients or arrange collections.

In **Plan next meal**, calculating a forecast automatically runs the **AI prep coach**. A fixed ridge model learns served kg per diner from strictly earlier services, calendar effects and declared events. It uses at most 56 training services, requires 28 earlier observations and five temporal validation services, and reports up to 14 rolling test errors against a recent served/diner baseline. Empirical residual scenarios show surplus and shortage; the shortage preference changes the preparation suggestion. These ranges are uncalibrated. Confirmed shortage in training prevents applying the suggestion because unmet demand may be censored. Managers choose the quantity. The approved plan retains the AI report and its training/test provenance.

Enable aggregate sharing and select **Brief me with Groq** for model-based priority selection from server-validated evidence. Groq cannot create quantities, add recipients, approve food or dispatch anything. Invalid responses or connection failures return the local briefing. Provider configuration appears in Field station; actual live checks are recorded in [AI Kitchen Advisor validation](AI_KITCHEN_ADVISOR.md).

## Separate measured operations workspace

No real KNSIT kitchen records have been supplied. Generated records remain labeled as practice data; they cannot create a real dispatch receipt. To start a clean database without touching the existing practice workspace, run this in the backend terminal:

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
$env:FOODWISE_DEMO='false'
$env:FOODWISE_DB='backend/operations.sqlite3'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Stop the existing backend first. Start the frontend as shown below. Record weighed meal observations with the measured source, or preview and import historical CSVs (uploads retain their unverified source). Sparse history requires a manual plan. The operations workspace starts empty and hides practice reset, fixture and simulated handoff controls. Its reset and simulated handoff endpoints are disabled. To return to practice, stop the backend, set `FOODWISE_DEMO='true'` and `FOODWISE_DB='backend/foodwise.sqlite3'`, then restart.

For Groq, copy `.env.example` to `.env` only if `.env` does not already exist. Set `GROQ_API_KEY` locally. The example uses `GROQ_MODEL=openai/gpt-oss-20b`, verified in the [official supported model list](https://console.groq.com/docs/models) on 9 Oct 2026; check availability in your account. Restart the backend. Never place keys in frontend code, `VITE_` variables, source control or chat.

This deliverable runs locally on loopback. It has no authentication, independently verified food measurements or recipient partnership contracts, and does not claim public production deployment or food-safety certification. See [docs/RECIPIENT_AI_VALIDATION.md](RECIPIENT_AI_VALIDATION.md) for the implementation and actual verification evidence.

## Windows PowerShell: first-time setup

Python 3.12+ and Node.js 22+ are required. Use `npm.cmd` to avoid PowerShell npm script execution-policy issues. Dependencies are already installed in this workspace; use these commands to reproduce installation on another machine:

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
Set-Location frontend
npm.cmd ci
```

If virtual environment creation leaves an environment without pip, run `python -m pip --python .venv install pip -r backend\requirements.lock.txt` from the root. This was needed in the Codex filesystem sandbox; a regular Windows Python installation normally includes `ensurepip`.

## Run: two terminals

Terminal 1, backend:

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
.\.venv\Scripts\python.exe -m backend.app.db
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, frontend:

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack\frontend'
npm.cmd run dev
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8000/docs**. Health: **http://127.0.0.1:8000/api/health**. Keep both terminals running; Ctrl+C stops each server.

SQLite automatically bootstraps on first launch and retains plans, actuals, review events, handoffs, inventory and immutable forecast snapshots across restarts. `backend/foodwise.sqlite3` is the default database. The backend reads simple assignments from root `.env` without executing or interpolating them; process environment values take precedence. For example, `$env:FOODWISE_DEMO='false'` disables demo reset. No secrets are required for the core workflow.

## What works

- Overview with full cooked-food accounting, daily mass chart, normalized evidence-backed findings and record drawer; date filters and dataset/source badges.
- CSV preview with row/field errors, strict mass balance, duplicate and nonfinite rejection, 5 MB / 10,000 row limits, server-issued hash-linked expiring tokens and atomic replacement. Source is always `user_provided_unverified` for uploads. Existing or archived IDs conflict; use distinct record IDs. Actual logs are retained. Old historical rows remain archived for saved report evidence. History linked to recovery cannot be replaced until demo reset.
- Attendance-aware forecasts of **served kg = consumed + plate waste**, last eight matching weekday/event rows when at least five exist, otherwise last fourteen item/meal observations. Recency weights, fallback reasons, descriptive 10th/90th percentiles, historical record IDs and rolling temporal MAE against a historical-mean baseline are exposed. Sparse history requires a manager-entered manual quantity with no invented forecast.
- Interactive per-item simulator: expected and point surplus/shortage, empirical shortage frequency, positive or negative estimated cost difference and untouched-surplus difference. Exact, unrounded quantities are approved; display is rounded.
- Manager-approved preparation sheets and actual meal entry, linked or unplanned. Live server validation enforces 0.02 kg row mass balance. Actuals update dataset version; stale forecasts cannot receive new approval. Piece-based API records require explicit measured piece weight and matching cooked kg.
- Deterministic recovery review, permanent backend block on plate-waste human redistribution, fail-closed unknown/missing/failed review, staff attestations, separate manager approval, approval invalidation on changes, category allocation limits and idempotent split handoffs. Demo compost/biogas processors must explicitly accept the material. All handoffs are simulated.
- Raw ingredient label-date and storage alerts, deterministic evidence reports, approved-vs-actual service errors, separately displayed recorded food, projected prevention and simulated disposition, audit trail and visibly confirmed demo reset.

## Three-minute judge walkthrough

The interface uses a bright **Living kitchen** design: a custom miniature landscape with explorable food streams and backend-calculated mass, a horizontal Observe → Prepare → Account → Review → Learn → Connect journey, and a responsive preparation simulator. Approved plans carry into linked meal logs; saved meals carry into recovery allocation. Optional optimization, model comparisons and measurement setup expand on demand. Open the **?** button in the header for the built-in judge guide.

See [docs/UI_UX_VALIDATION.md](UI_UX_VALIDATION.md) for the redesign, browser checks and preview screenshots. The overview navigation label is **The big picture**.

Use [docs/DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md) for exact clicks and the original [judge script](06_JUDGE_DEMO.md) for talking points. Demo date: **2026-10-09**; inventory checks use the selected date, not the host clock.

1. **Overview:** identify Friday rice surplus, inspect historical records, and show source labels. These are synthetic associations, not causal proof.
2. **Plan next meal:** keep 2026-10-09 lunch, 160 diners, no event, 5% buffer. Calculate; select Rice; lower and raise cooked quantity to show both shortage and surplus. Read the computed backtest. Approve as Demo manager and generate an evidence explanation.
3. **Record meal:** load the separate 100 kg fixture. Confirm 82 consumed + 10 untouched + 8 plate waste, and **90 kg served**. Save the synthetic actual.
4. **Recovery:** allocate 10 kg untouched lunch surplus. Complete the five handling checks and batch-manager approval, explicitly load/save the synthetic holding example, check dinner demand, enter a manual 20 kg total when dinner history is insufficient, reserve 10 kg, and approve as the qualified demo kitchen manager. This revises dinner to 10 kg fresh + 10 kg reused. Log dinner against that approved plan: 20 total / 18 consumed / 1 untouched / 1 plate. Then allocate lunch's 8 kg plate waste, demonstrate the backend human-handoff block, confirm segregation, estimate biogas potential and record a simulated accepted-processor handoff. Do not hand off the same surplus reserved for dinner.
5. **Impact & evidence:** show recorded reuse, fresh-food provenance, simulated handoffs and theoretical energy separately. Actual energy is not measured. A future Mixed cooked meal dinner forecast includes the new dinner actual, but still requires manual quantities while history is sparse. Return to Overview, review synthetic tomato label/storage/condition evidence, and inspect offline raw-ingredient recipe alternatives and procurement shortages.

For a direct feedback demonstration, log an actual against a Rice plan, then forecast a later matching weekday. Plans and snapshots remain fixed; fresh requests and temporal backtests incorporate only observations earlier than their target date.

## Research-based improvements

See [docs/RESEARCH_REVIEW.md](RESEARCH_REVIEW.md) for primary papers, GitHub source/commit/license review, adoption decisions, access limitations and reproducible results. [docs/RESEARCH_PLAN.md](RESEARCH_PLAN.md) records hypotheses before experiments.

- **Cost-aware preparation:** in Plan next meal, calculate a forecast and choose an item. Expand **Explore a cost-aware preparation choice**. Enter surplus/shortage penalty assumptions, kitchen capacity and maximum historical shortage frequency. Find a quantity, inspect expected surplus/shortage and scenario loss, explicitly use it in the preparation sheet, then approve. The offline report retains those decision assumptions. Infeasible constraints never produce an automatic recommendation. Penalties are scenario inputs, not measured loss or savings.
- **Forecast challengers:** expand **Look inside the forecasting models** to inspect five earlier-only rolling comparisons expose MAE/RMSE/bias/WAPE, every training record and actual range coverage. The experimental fixed calendar ridge does not replace P0. Actual attendance is known during evaluation. These synthetic results are not real-kitchen validation.
- **Shortage-aware evidence:** meal logs accept unknown / no reported shortage / confirmed shortage. CSV may optionally include `service_shortage_reported` with true/false/blank. Blank or absent is unknown. Confirmed shortages in the selected sample block automatic cost optimization; served food cannot reveal unmet demand. Manual manager review remains available.
- **Portion measurement:** in Impact & evidence, expand **Set up a measurement protocol** to register an approved future trial using actual logs, or load clearly labeled synthetic retrospective settings. Compare plate waste, consumed, served and untouched grams per diner, with source/event/shortage context and historical IDs. At least five distinct services per phase are required to show a difference; this demo minimum is not a statistical power calculation. Optional seconds remain available. Retrospective comparisons do not claim that an intervention occurred or caused savings.

New API routes: `POST /api/optimize`, `POST /api/trials`, `GET /api/trials`. Plans optionally link `decision_ids` by item; the backend verifies forecast, item and exact quantity before retaining the decision. SQLite migrations add two tables without discarding existing prototype state. Reset includes these demo decisions/protocols.

Reproduce the isolated synthetic experiment (reads original history, not mutable SQLite):

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
.\.venv\Scripts\python.exe -m scripts.research_experiment
```

The result is saved to `docs/research_results.json`. No internet, model download or API key is needed. The research cache script is optional and only downloads public text for review; application startup never uses it.

## Reset / CSV rehearsal / validation

The topbar reset button asks for visible confirmation and clears only this seeded demo database. CLI reset (also clears demo decisions):

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
.\.venv\Scripts\python.exe -m backend.app.db --reset
.\.venv\Scripts\python.exe scripts\make_demo_imports.py
```

Upload `artifacts\invalid_history_upload.csv` to exercise validation. `artifacts\valid_history_upload.csv` contains the original history with distinct upload IDs, so it can demonstrate preview and commit without editing source files. Reset after rehearsal. Do not replace forecast history with `data\demo_accounting.csv`.

Run checks:

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
.\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm.cmd run typecheck
npm.cmd run build
npm.cmd audit
```

Tests use isolated temporary databases. In the Codex sandbox, tests and Vite required normal host filesystem access; the tests themselves do not access the demo database. Detailed executed results are recorded in [VALIDATION.md](../VALIDATION.md).

## Boundaries

P0 plus focused research, circular-kitchen and Field station extensions: no authentication, autonomous agents, vector database, IoT or real NGO integrations. Optional Groq, Gemini and OpenRouter adapters curate server-authored evidence cards; they cannot generate displayed facts, change calculations or approve actions. The deterministic report remains the complete offline explanation mode. Historical uncertainty is descriptive; evaluation uses known actual attendance and is not field validation. Estimated production costs and projected surplus differences are not measured savings. Recovery eligibility is an illustrative staff policy workflow, not food-safety certification. Production use requires kitchen-approved procedures and qualified review. Uploaded and staff-entered data retain explicit source labels. Missing shortage flags limit latent-demand inference. Offline recipe suggestions use reviewed raw-ingredient inventory; cooked yield and nutrition planning remain deferred. Dinner reuse supports the documented same-day hot-holding demo path and identical cooked dishes only. Other handling modes remain blocked. Biogas output is illustrative potential; actual measured energy is not recorded.

Tailwind 4 uses the current [official PostCSS installation](https://tailwindcss.com/docs/installation/using-postcss). Fonts and visual assets are local. External maps, weather, place search and provider calls occur only after their respective user actions; none is required for the kitchen workflow.


## Circular kitchen extension

The existing UI and algorithms are preserved. Recovery now includes **Lunch → dinner** and **Biogas potential**; Overview includes **Near-expiry recipe ideas**; Impact includes **Reuse & recovery outcomes**. The complete application still runs offline without an API key or new packages.

See [the implementation audit and exact changed files](CIRCULAR_KITCHEN_IMPLEMENTATION.md), [executed checks and limitations](CIRCULAR_KITCHEN_VALIDATION.md), and [the connected judge walkthrough](DEMO_WALKTHROUGH.md#connected-circular-kitchen-demonstration-three-minutes). That extension's verification recorded **86 backend tests passed**, TypeScript passed, production build passed, and the connected scenario was exercised in the browser. Existing database rows were retained and backed up; startup adds the reuse ledger without resetting data.

Use the same two-terminal Windows commands above. Do not run `--reset` to start the app. If DEMO-100 already exists, inspect its retained batches/outcomes or choose a new unique synthetic record ID; never overwrite an existing meal just to rerun a demonstration.

## Living kitchen and KNSIT Field station

The overview now has a custom, locally bundled landscape illustration with selectable preparation, service, untouched-surplus and plate-waste streams. Every mass value comes from the overview API and respects its date filters. Motion has a pause control and respects reduced-motion preferences. The landscape is conceptual, not an image of actual campus facilities.

Open **Field station** at `http://127.0.0.1:5173/#station`. The default approximate campus entrance point comes from [KNSIT's published facilities document](https://knsit.com/wp-content/uploads/2024/05/7.1.1_Facilities_Provide_in_Campus.pdf). Open the interactive OpenStreetMap view or explicitly fetch current Open-Meteo weather. Weather is a model estimate with observation/retrieval timestamps, cached for ten minutes; stale fallback is labeled and expires after an hour. Outdoor weather does not establish food holding temperatures and does not silently alter the served-demand forecast. City search and manual coordinates are available; changing the location clears previous conditions. Location preferences stay in this browser.

The evidence desk offers an offline briefing and optional provider curation. To connect a provider, create the server-only file **once** (do not overwrite an existing `.env`):

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
if (!(Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad .env
```

Set the desired `GROQ_API_KEY` + `GROQ_MODEL`, `GEMINI_API_KEY` + `GEMINI_MODEL`, or `OPENROUTER_API_KEY` + `OPENROUTER_MODEL`. Use an exact JSON-capable model identifier available in your account; no model name is guessed or auto-selected. Restart the backend using the normal command above, then reload Field station. The status ledger reports configuration, never keys. The app requests confirmation to share only aggregate food evidence with the selected provider for a briefing. The provider can select existing evidence IDs; all displayed text and quantities remain server-authored. Unconfigured providers, HTTP failures, invalid JSON and invented evidence fall back offline. No tools, agents, automatic routing or safety decisions are delegated to an LLM.

See [design, integration notes and executed checks](LIVING_KITCHEN_VALIDATION.md). At the initial field-station implementation, **112 tests** and the frontend checks passed; keys had not yet been configured. The later live provider checks and **163-test** suite are documented below.

## AI Kitchen Advisor

Open **AI Kitchen Advisor** in the main navigation, or visit **http://127.0.0.1:5173/#advisor**. This separate read-only chat section uses existing saved forecasts, inventory eligibility checks, waste investigations, recovery rules, recipient acceptances and the NGO map's cached directory. Existing workflows and SQLite records are preserved. It adds `GET /api/advisor/capabilities` and `POST /api/advisor/chat`.

Choose Groq (default) or Gemini, then explicitly enable aggregate evidence sharing to use AI. Your typed question and conversation stay local; the model sees recognized topics and server-authored evidence with temporary aliases. AI prioritizes evidence; it cannot author quantities, override safety, approve food or perform actions. Offline mode supports the same structured kitchen topics. Unsupported questions receive an honest scope message. History stays in memory across page navigation, up to 24 turns, and clears with **New Chat** or a full reload.

Groq `openai/gpt-oss-20b` and Gemini `gemini-flash-lite-latest` passed actual authenticated JSON generation and advisor tests on 9 Oct 2026. Gemini's model alias was discovered from its catalog and configured locally. OpenRouter's supplied key returned **HTTP 401**; replace it with a valid key and set an available JSON-capable `OPENROUTER_MODEL` before using it. Keys were never printed or copied into frontend code. The public example contains model IDs only.

Try **How much rice should we prepare on 2026-10-09 for lunch?**, **Which ingredients are nearing expiry?**, or **Which nearby NGOs are shown on our map?**. Expand **Evidence & data references** to inspect source labels, snapshot IDs and linked meal records. A missing or stale forecast produces no invented quantity. “Tomorrow” uses Asia/Kolkata time; optional planning context must agree with the question. Student Meal Pulse does not exist in this repository, and the advisor says so. Directory summaries use the saved Field station location, the existing 15 km default, cached discovery timestamps and the same published contacts; listings never establish acceptance.

Repeat the explicit live key check (small network requests; not part of startup or automated tests):

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
.\.venv\Scripts\python.exe scripts\check_ai_providers.py
```

See [exact files, response examples, verification results and limits](AI_KITCHEN_ADVISOR.md). Final verification: **163 backend tests passed**, including 32 new advisor tests; TypeScript and production build passed; live Groq/Gemini and browser workflows passed. One pre-existing Starlette/httpx deprecation warning remains.
