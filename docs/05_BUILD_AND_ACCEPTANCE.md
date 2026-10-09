# Build order and completion
Hour 0–1: repo inspection, data schemas, SQLite seed, validation and fixture loader.
Hour 1–3: forecasts, temporal backtest, simulator, mass balance, recovery state machine tests.
Hour 3–5: overview, plan, simulator and actual-meal UI wired to API.
Hour 5–7: recovery approval/handoff, expiry alerts, evidence drawer and deterministic report.
Hour 7–8: end-to-end verification, README, demo reset and rehearsal. Extra 4 hours: optional provider adapter, UI polish, curated recipes. If only 6 hours, skip provider adapter and recipes; keep real forecast and deterministic evidence explanations.
## Acceptance scenarios
1 Load supplied synthetic history; totals obey mass balance; source badge always visible.
2 Upload invalid CSV: negative, NaN, duplicate, malformed date, bad balance → actionable row errors and no mutation.
3 Forecast is reproducible, references historical rows, uses only prior dates, exposes fallback; sparse history requires manual input. Temporal MAE is computed, not hardcoded.
4 Simulator reduces Q: surplus falls and shortage may rise. Negative savings are displayed correctly. Exact fixture samples 78/82/86 and Q=85 yield mean surplus=10/3kg, shortage=1/3kg, shortage frequency=1/3; Q=100 yields surplus=18kg and shortage=0.
5 Approve plan; restart backend; plan remains. Record actuals 100/82/10/8 and served=90kg. This example is an actual accounting fixture, not a demand forecast of 82kg.
6 Attempt plate-waste redistribution with all checks true → blocked by backend. Missing untouched safety evidence → no approval. Complete checks → eligible, still requires manager approval. Changing evidence clears approval.
7 Duplicate handoff cannot increment total; split handoffs cannot exceed available amount; unknown processor acceptance → review required.
8 Expired/unknown-storage ingredient never suggested as safe; near expiry label is a date warning only.
9 Disconnect network/remove API key: complete demonstration works with explanation_mode deterministic.
10 New actuals change active dataset version and next forecast without contaminating past evaluation. Recovery and avoided-waste counts remain separate.
11 Frontend TypeScript/build pass. Domain tests cover formulas, leakage prevention, mass balance and transitions. Local browser smoke check covers upload → forecast → approve → actuals → blocked plate donation → simulated recovery.
## Deliverables from implementing Codex
Working frontend/backend, dependencies, .env.example, README with separate terminal launch commands and seed/reset commands, tests, screenshots if available, and actual check results. No unresolved placeholder buttons in P0.
