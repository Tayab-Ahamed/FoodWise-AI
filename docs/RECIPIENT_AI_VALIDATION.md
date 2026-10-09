# Recipient network and required planning AI

Implemented and verified on Windows, 9 October 2026. Original numbered specifications, supplied data and references remain preserved. SHA-256 comparison against `artifacts/circular-source-hashes.json` checked 14 original files: none changed.

## What changed

- A Leaflet 1.9.4 recipient atlas replaces the single-marker embedded map. Staff request an Overpass search around the selected kitchen, within 5–30 km. The backend validates coordinates, bounds response size, rejects incomplete responses, deduplicates named features, computes great-circle distances and sorts results. OSM tags identify NGOs, social facilities, food banks, soup kitchens and organic processing candidates. Coverage is incomplete. Positions and distances do not establish food acceptance or a partnership.
- Live directory snapshots are retained in SQLite and survive application restarts. Fetch time remains visible. An outage preserves the previous snapshot with stale status; official and staff-saved contacts remain available. No external query runs merely by opening the directory. Opening the map loads OSM tiles; discovery explicitly sends the selected public campus/search coordinates to Overpass.
- Official Bangalore Food Bank and Robin Hood Army contact entries provide source links. Collection coordinates are left blank when unverified. A sourced Bangalore Food Bank contact was saved during browser verification; no contact attempt, acceptance or handoff was invented.
- Recipient acceptance is specific to a batch, origin, route, quantity, contact person and evidence, expires within 24 hours, and is a staff attestation. A completed dispatch requires a measured source record, receiver, receipt reference, segregation and capacity. Human recovery additionally requires current documented review and manager approval. Plate waste and unknown origin are blocked from human redistribution. Atomic SQLite allocation includes reuse and every existing handoff. Idempotent retries return the original immutable receipt; changed intent conflicts. Actual and simulated disposition totals are separate.
- Calculating a forecast automatically runs the local AI prep coach. Fixed NumPy ridge regression learns served kg per diner from strictly earlier dates, weekday, event and bounded trend. The target includes plate waste. It trains on up to 56 observations, needs at least 28 prior records and five temporal validation services, and reports up to 14 rolling evaluations. No calendar model is silently substituted for the existing P0 forecast. The manager explicitly applies a suggestion and approves the final preparation quantities.
- Residual scenarios scale out-of-sample errors per diner to expected attendance. The shortage-to-surplus preference selects an empirical scenario quantile. Both expected surplus and shortage are displayed. The 10–90% envelope is uncalibrated; frequencies are descriptive, not service guarantees. Confirmed shortages in training block applying a suggestion because served mass may censor unmet demand. Sparse history produces a data-collection state, never fabricated predictions.
- Groq is the default connected briefing provider. It receives only predefined aggregate model evidence after staff sharing consent, and can return only existing evidence IDs. Server-authored quantities and prose are displayed; unknown IDs, duplicates, extra fields, failed requests and missing configuration fall back to local evidence. The approved preparation plan retains the AI report, training/test IDs, model version, source labels and Groq status. No autonomous agent or model safety approval was added.
- The existing practice database remains intact. `FOODWISE_DEMO=false` with `FOODWISE_DB=backend/operations.sqlite3` starts an empty measured-operations workspace, hides practice controls, and disables reset, fixture and simulated handoff endpoints. Generated data cannot create a real dispatch receipt. Upload provenance remains unverified; staff can log measured observations explicitly. No real KNSIT meal records were supplied.
- The Field station is loaded as a separate frontend route so Leaflet is not included in the main application bundle.

## Primary sources checked

- [Bangalore Food Bank official donation contact](https://bangalorefoodbank.com/get-involved.html): Yelahanka address, food-donation email and public phone. This supports directory contact information only.
- [Robin Hood Army official site](https://robinhoodarmy.com/): volunteer food-rescue network. Local availability and collection point need confirmation.
- [OSM Overpass QL](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL), [food bank tagging](https://wiki.openstreetmap.org/wiki/Tag:social_facility%3Dfood_bank), [Leaflet quick start](https://leafletjs.com/examples/quick-start/): query semantics, community directory data and map attribution. Leaflet is pinned to stable 1.9.4; version 2 alpha examples were not copied into the 1.9 implementation.
- [Groq supported models](https://console.groq.com/docs/models), [structured output documentation](https://console.groq.com/docs/structured-outputs): configured model IDs and constrained JSON handling. `.env.example` specifies `openai/gpt-oss-20b`, listed by the provider at verification time. Availability remains account-dependent. No SDK interface or unavailable API key was fabricated.

## Actual automated results

Commands from the project root, with frontend commands run in `frontend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q --tb=short --basetemp artifacts/pytest-recipient-release
```

**131 passed, 1 warning, 11.06 seconds.** Includes the original 112 tests and 19 recipient/AI cases. Coverage includes upstream validation/cache/stale behavior, cache persistence, recipient source URLs, capacity and atomic concurrent dispatch, idempotency conflicts, real/simulated accounting separation, generated/unverified dispatch rejection, plate waste, current review, acceptance expiry, changed batch invalidation, processor acceptance, segregation, AI temporal provenance and target, monotonic shortage preference, sparse history, shortage-censored training, Groq sharing/invalid output/fallback, plan evidence binding, and clean operations bootstrap/source status.

One preexisting Starlette TestClient/httpx deprecation warning remains. The initial sandbox-only pytest attempt failed to create/access Windows temporary files; the host-access test run above completed successfully. Domain checks do not require the public directory or Groq to be online.

```powershell
npm.cmd run typecheck
npm.cmd run build
```

Both completed successfully. Final Vite 6.4.4 build: **2,188 modules, 5.47 seconds**, no large-chunk warning after route splitting. Main JS 339.29 kB (gzip 100.70), station JS 177.80 kB (gzip 52.31), charts JS 431.64 kB (gzip 124.06). Main CSS 57.38 kB; station CSS 15.61 kB.

## Actual browser and live-service checks

Backend and Vite were started on `http://127.0.0.1:8000` and `http://127.0.0.1:5173` and left running. The in-app browser exercised:

1. Discovery initially returned unavailable; retry returned real directory data. A fresh live fetch at **2026-10-09T09:50:55.890751+00:00** returned **59 mapped candidates** within 15 km. The source response is retained in `artifacts/recipient-directory-live.json`; the database snapshot survived backend restart. These are directory candidates, not 59 confirmed food recipients.
2. Map rendered OSM tiles and 60 circles (59 candidates plus the kitchen). Selecting Kirubai Project opened its sourced popup/detail. Zoom control worked. No collection point was invented for official contacts without verified coordinates.
3. Saved the official Bangalore Food Bank contact through the UI, with unknown coordinates left blank. The saved recipient appeared in Recovery's separate acceptance form. No acceptance was recorded for the organization.
4. Calculated a 160-diner lunch forecast, trained the coach, applied the Rice suggestion, attempted a Groq briefing with consent and verified the explicit missing-key fallback. Approved practice plan `plan-852ae3756c644260` retains its AI evidence and `groq_status=not_configured` in SQLite.
5. At that forecast, learned model/recent-baseline temporal MAE was approximately Dal **1.03/0.94 kg**, Rice **1.66/1.56 kg**, Vegetable Curry **1.10/1.13 kg**. The richer calendar model does not outperform the recent-ratio baseline on every dish. The UI discloses this result and does not claim validated KNSIT performance or automatically promote the learned model.
6. Checked map at 320, 390 and 1440 px, and AI coach at 320, 390, 768 and 1440 px: no horizontal document overflow. Restored the browser's default viewport. The final console error query returned an empty list.
7. Verified 274 existing food records, dataset version 8 and zero real dispatch receipts; the existing meal records were not reset or relabeled. One sourced recipient contact and the browser-approved practice preparation plan were added.

Screenshots: `artifacts/recipient-network-browser.png` and `artifacts/ai-prep-coach-browser.png`.

## Remaining limits

No Groq key is configured, so real authenticated provider calls were not run. Wire format, strict validation and fallback behavior were tested with controlled responses. Live Groq use needs a backend key and an account-available model ID.

Kitchen history remains generated practice data. Real measured performance, food acceptance and completed handoffs need operational evidence. Public OSM data can be outdated, incomplete or incorrectly categorized; map distances are straight-line, not driving routes or arrival estimates. Map tiles and live refresh depend on public network services. There is no NGO messaging or automatic dispatch. Contact attestations and measured source labels are staff claims, not independent verification. Food eligibility is policy review, not safety certification.

This is a local application without authentication or a public deployment. It does not claim multi-tenant production readiness, partner contracts, measured energy production or measured environmental savings.
