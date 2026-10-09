# Executed verification — 2026-10-09

These are actual checks performed in the selected Windows workspace, not planned checks.

**Research upgrade:** the later run passed **45 tests**, frontend type/build and dependency audit. Research features, browser checks and exact current results are documented in [docs/RESEARCH_VALIDATION.md](docs/RESEARCH_VALIDATION.md). The table below records the original P0 run and should not be mistaken for the latest test count.

| Check | Executed result |
|---|---|
| Domain / supplied acceptance scenarios | **30 passed** in 2.75 seconds, using isolated SQLite databases. |
| Frontend TypeScript | `npm.cmd run typecheck` **passed**. |
| Production build | `npm.cmd run build` **passed**, Vite 6.4.4, 2,173 modules; final build 5.74 seconds. |
| Frontend dependency audit | `npm.cmd audit`: **0 vulnerabilities** after moving the build chain to Tailwind 4. |
| Local backend | FastAPI / Uvicorn started successfully at `127.0.0.1:8000`; stopped and restarted during verification. |
| Local frontend | Vite started successfully at `127.0.0.1:5173`; exercised in the Codex in-app browser. |
| Browser runtime errors | Browser developer log error query returned an empty list at the end of the walkthrough. |
| Loaded responsive overview | Tested widths **320, 768, 1024, 1440 px**. Document scroll width equaled client width at each breakpoint. |
| Demo reset | Visible browser confirmation executed. Restored **270 synthetic historical records / 90 services**, dataset version 4, and cleared rehearsal decisions. |

The test run emitted one non-failing dependency warning: Starlette's TestClient currently deprecates its `httpx` adapter in favor of `httpx2`. No domain failures remain. Initial sandbox test runs could not create pytest temporary directories; initial Vite build was blocked by Windows sandbox `realpath` permissions. Both were rerun with normal host filesystem access, successfully. These restrictions were tooling issues, not waived application checks.

## Domain coverage

- Seed mass balance and source labels; accounting fixture absent from default forecast history.
- Invalid CSV negative/nonfinite values, ISO date errors, attendance/event errors, duplicate/existing IDs, correct source row numbers even after invalid rows, 5 MB and 10,000 row limits, no mutation on preview errors.
- Server-issued hashed preview tokens, forged/used token rejection, atomic activation, stale preview conflict, preserved historical evidence after replacement, uploads forced to unverified source.
- Recency-weighted **served** demand including plate waste, reproducibility, descriptive percentile ranges, fallback explanations and sparse manual planning.
- Strict earlier-date training for forecasts and all temporal backtest observations, independently recomputed model and baseline MAE, future actuals not changing past evaluation.
- Exact fixture `[78, 82, 86]`, Q=85: surplus **10/3 kg**, shortage **1/3 kg**, shortage frequency **1/3**; baseline Q=100: surplus **18 kg**, shortage **0 kg**. Negative cost differences tested.
- Approved plan persistence across a restarted application, mass-balance rejection, fixture served **90 kg**, version advancement, stale forecast rejection and changed future matching-weekday forecasts.
- Piece counts require explicit measured piece weight and matching cooked kg; nonfinite actuals rejected.
- Plate waste blocked from human redistribution even with every check true; unknown origin, missing/failed checks, manager approval and evidence/quantity/origin invalidation.
- Duplicate keys return the same receipt; changed requests conflict; split dispositions and batch allocations cannot exceed category mass. Concurrent allocations are serialized: only one of two 6 kg requests against 10 kg succeeds.
- Unknown processor acceptance blocked; accepted compost and human routes counted separately; date-based expiry and unknown storage warnings; zero-waste / empty-data states; explicit demo reset guard; deterministic reports.

## Browser walkthrough completed

1. Uploaded `artifacts/invalid_history_upload.csv`: row/field errors displayed; active history stayed at 270 records.
2. Previewed `artifacts/valid_history_upload.csv`: 270 valid rows, hash and explicit replacement checkbox. Confirmed atomic import; active history source became user provided, unverified.
3. Calculated lunch forecasts for 160 diners on 2026-10-09. Rice served demand displayed **38.2 kg** from eight prior observations. Backtest displayed Rice model MAE **1.74 kg**, baseline **4.75 kg**, 14 evaluations; Dal and curry evaluations were also computed.
4. Lowered Rice preparation to **30 kg**: projected surplus **0.0 kg**, shortage **8.0 kg**, empirical shortage frequency **100%**. At **40 kg**: surplus **2.1 kg**, shortage **0.1 kg**, frequency **25%**. Approved the exact preparation plan in SQLite.
5. Loaded and saved the separate accounting fixture: **100 kg prepared / 82 consumed / 10 untouched / 8 plate**; live server validation showed **90 kg served** and zero balance residual.
6. Created plate-waste batch and attempted human handoff: backend returned “Plate waste is always blocked from human redistribution.” Created untouched batch and attempted approval with missing evidence: backend rejected it with named missing checks.
7. Recorded all five passed demo staff attestations, saved review, obtained separate manager approval, and recorded a **5 kg simulated human handoff**. Repeated the same request: identical receipt; recorded total stayed **5 kg**.
8. Impact screen showed logged actual food, approved-plan projections and simulated route totals separately. Generated the deterministic offline evidence report with historical IDs and assumptions. No provider or API key was configured.
9. Restarted the backend and reloaded the frontend; rehearsal records and dataset version persisted. Tested responsive overview widths, opened 90 historical Rice evidence rows, and dismissed the native dialog using Escape.
10. Executed the visible reset and restored the original synthetic judging dataset. Both local services were left running.

Screenshots: [restored desktop overview](artifacts/overview-desktop.jpg), [completed impact walkthrough](artifacts/impact-browser.jpg). The impact screenshot records the earlier import rehearsal before the final dynamic source-banner correction; individual actual source and simulation labels were already visible. The final overview screenshot shows the restored source labels.

## Remaining boundaries

P0 is implemented. P1 recipes and optional provider integration were intentionally omitted. The complete application uses local assets and deterministic explanations after dependency installation. It demonstrates policy review and simulated handoffs, not certified food safety or real redistribution. Historical ranges and synthetic backtests are not field-validation claims; financial and prevention effects are projections. No deployment or external partner integration was attempted.


## Circular kitchen extension — 9 October 2026

Latest executed checks: **86 backend tests passed, 0 failed**, 22.00 s; frontend typecheck passed; production build passed (Vite 6.4.4, 2,178 modules, 9.58 s). Baseline before extension: 45 passed, type/build passed, no baseline failures. One existing non-failing TestClient/httpx deprecation warning remains. Connected reuse/biogas/recipe browser checks and preservation comparison passed; original data/spec files are unchanged and existing SQLite rows are retained.

See [the full executed extension verification](docs/CIRCULAR_KITCHEN_VALIDATION.md) and [feature audit, migration and exact files](docs/CIRCULAR_KITCHEN_IMPLEMENTATION.md). Earlier verification records above are historical results, not claims about the expanded suite.
# Latest extension: Living kitchen and Field station (2026-10-09)

The full backend suite after the sustainability extension passed **112 tests** (one existing Starlette/httpx deprecation warning); frontend TypeScript and production build passed. Live KNSIT map rendering, timestamped Open-Meteo conditions, city search, browser location persistence, offline map return, food-stream interactions, provider consent and unconfigured fallback were exercised. Overview and Field station fit 320/390/768/1440 px without horizontal overflow. All 14 original source hashes remain unchanged; the retained database remains at 274 records and dataset version 8. Real keyed provider inference has not been tested.

See [the full extension evidence, sources and limitations](docs/LIVING_KITCHEN_VALIDATION.md). Earlier entries below describe their respective implementation stages.
# Recipient network and AI prep coach — 9 October 2026

Release verification: **131 domain tests passed** (11.06 s, one preexisting TestClient deprecation warning); frontend TypeScript passed; production Vite build passed (2,188 modules, 5.47 s). Live Overpass fetch returned 59 sourced candidates around KNSIT; browser verified map pins, contact saving, AI suggestions, manager approval with retained evidence, Groq missing-key fallback and responsive layouts. No real dispatch or NGO contact was performed. Original source hashes unchanged (14 files).

See [docs/RECIPIENT_AI_VALIDATION.md](docs/RECIPIENT_AI_VALIDATION.md) for exact checks, source links, launch modes, evidence and remaining limitations.
