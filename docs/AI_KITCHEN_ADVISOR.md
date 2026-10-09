# AI Kitchen Advisor — implementation and executed validation

Date: 9 October 2026. This is an additive section; the dashboard, map, forecasting engine, preparation simulator, recording, recovery and impact workflows retain their existing implementations. Original specifications and datasets are preserved. All 14 files in `artifacts/circular-source-hashes.json` were checked and remain unchanged.

## Files

Created:

- `backend/app/advisor.py` — strict request validation, capabilities and chat endpoints, constrained provider selection, mandatory evidence and offline fallback.
- `backend/app/advisor_evidence.py` — consistent SQLite read snapshot with `PRAGMA query_only=ON`; existing forecast, inventory, accounting, investigations, map-directory, acceptance and processing evidence.
- `backend/tests/test_advisor.py` — 32 isolated tests, including parametrized scenarios.
- `frontend/src/pages/AdvisorPage.tsx` — separate chat page, suggested questions, provider controls, explicit sharing, session conversation, New Chat, errors, loading, planning context and evidence links.
- `frontend/src/pages/advisor.css` — styles scoped to the advisor, matching the existing paper/forest theme.
- `scripts/check_ai_providers.py` — explicit live credential/model smoke check with sanitized output; no keys or upstream error bodies printed.
- `docs/AI_KITCHEN_ADVISOR.md` — this implementation and validation record.

Modified:

- `backend/app/main.py` — import and register the advisor router.
- `frontend/src/App.tsx` — one lazy page and one navigation item.
- `frontend/src/sustainability.css` — seven navigation slots; mobile final item spans the row.
- `.env.example` — document advisor use and the live-tested Gemini model alias; no credentials.
- `README.md` — configuration, examples, commands and current validation results.
- Local ignored `.env` — set only `GEMINI_MODEL=gemini-flash-lite-latest`; preserve every key and other setting. Do not distribute this file.

Generated verification artifacts:

- `artifacts/ai-provider-checks.json` — sanitized authenticated provider results.
- `artifacts/advisor-live-checks.json` — actual running-backend responses and SQLite preservation result.
- `artifacts/ai-kitchen-advisor-browser.png` — browser screenshot.

## Routes and behavior

Frontend: `http://127.0.0.1:5173/#advisor`.

Backend: `GET /api/advisor/capabilities`, `POST /api/advisor/chat`.

Example body:

```json
{
  "question": "How much rice should we prepare on 2026-10-09 for lunch?",
  "provider": "groq",
  "share_aggregate_evidence": true,
  "history": [],
  "planning_date": null,
  "meal": null
}
```

Use `provider: "offline"` without sharing for a completely local answer. The request also accepts the existing map location coordinates and a 1–30 km radius; the page reuses the saved Field station location with the existing 15 km default. Questions are limited to 1,000 characters, recent question context to eight entries. Extra fields, nonfinite coordinates, invalid dates, empty questions and conflicting context are rejected.

Each reply contains its mode, provider status, answer, evidence cards, source labels, dataset version, planning context, reference IDs, timestamp and limitations. Record references open the existing evidence drawer. At most 200 references per evidence card are returned, with an explicit total count. Inventory and forecast answers cap at 30 entries and disclose truncation.

The backend reads existing services rather than invoking endpoints that save forecast or coach snapshots. It retrieves the latest current-version snapshot per meal/item, preserving each snapshot's attendance and buffer assumptions. Missing, stale or sparse forecasts remain unavailable/manual; no number is generated to fill the gap. Inventory uses the existing date/storage/condition/staff-review eligibility function. Waste rates compare consecutive seven-day windows ending at the latest logged date; available coverage and confounders are disclosed. Existing investigations and portion-trial guidance distinguish association from causation.

The directory is read from the same SQLite snapshots as the NGO map, without discovery requests or writes. A listing is not food acceptance. Acceptance evidence separately counts unexpired declarations with unchanged batch origin/quantity and unused accepted capacity. It identifies these as staff attestations, not independent verification or authorization. Existing safety, measured-source and dispatch gates remain authoritative. Plate waste is always blocked from human redistribution. Simulated handoffs and theoretical energy remain labeled.

## AI boundary and privacy

This implementation reuses the existing documented backend provider adapter. One model call prioritizes up to three of at most 24 compact evidence cards. The model returns temporary evidence IDs only; strict validation rejects unknown IDs, duplicate IDs, extra prose/fields and invalid JSON. The server restores required forecast, inventory, acceptance, plate-waste and approval evidence regardless of the model's choices. Response labels say **AI-assisted**, accurately reflecting model prioritization of server-authored facts.

No autonomous agents, agent frameworks, tools, actions, browsing loops or vector databases were added. The advisor is deliberately not an unrestricted general-purpose chat model. Topic matching and short follow-ups run locally. Raw questions, conversation history, staff names, private review notes, internal record IDs and coordinates are not sent to providers. Public directory addresses/contacts and aggregate kitchen evidence may be shared only after the checkbox is enabled. Keys remain in backend environment variables.

Provider failures, timeouts, refusal/invalid output and missing configuration produce a clearly labeled deterministic response. The shared HTTP adapter uses fixed provider endpoints, no redirects, connection/read timeouts and bounded provider response size. Chat history is memory-only, bounded to 24 turns, survives page navigation and clears on reload/New Chat. Pending requests retain their session state across navigation. No chat tables or database migration were introduced.

## Configuration and actual provider checks

Keep root `.env` private. Do not overwrite an existing `.env` with the example. Restart the backend after changes.

```dotenv
GROQ_API_KEY=your_private_key
GROQ_MODEL=openai/gpt-oss-20b
GEMINI_API_KEY=your_private_key
GEMINI_MODEL=gemini-flash-lite-latest
OPENROUTER_API_KEY=your_private_key
OPENROUTER_MODEL=an_exact_available_json_capable_model_id
```

These placeholder key values are documentation only. Groq is the default selected connected provider; sharing is off until explicitly enabled. Provider presence in the configuration ledger does not prove inference works.

Executed authenticated smoke checks:

| Provider | Model | Auth/catalog | JSON generation | Result |
|---|---|---|---|---|
| Groq | `openai/gpt-oss-20b` | 200 | 200, validated | Working |
| Gemini | `gemini-flash-lite-latest` | 200 | 200, validated | Working; configured locally |
| OpenRouter | No model configured | 401 | Not attempted | Key rejected; replacement required |

An initial Gemini test using the catalog-listed `gemini-2.5-flash-lite` returned 404. The catalog-listed current flash-lite alias succeeded; this is the locally configured model. No hidden retries or model guessing are used in the application. The opt-in smoke script may discover a suitable model for testing when a model setting is empty, without modifying `.env`; OpenRouter discovery restricts itself to catalog-listed free JSON-capable text models after successful authentication.

Interfaces were checked against primary documentation: [Groq structured output](https://console.groq.com/docs/structured-outputs), [Gemini model catalog](https://ai.google.dev/api/models), [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output), [OpenRouter authentication](https://openrouter.ai/docs/api_reference/authentication), [OpenRouter key status](https://openrouter.ai/docs/api_reference/limits), and [OpenRouter structured output](https://openrouter.ai/docs/guides/features/structured-outputs). Model availability and aliases may change; run the explicit check for your account.

## Actual response examples

From the preserved current workspace, dataset version 8:

- **Rice for 2026-10-09 lunch:** saved preparation recommendation **40.13 kg** for **160 expected diners** with **5% buffer**; predicted served demand **38.22 kg**, including plate waste; descriptive historical range **35.97–40.47 kg**, using **8 earlier records**. This is a saved suggestion, not an approved plan or calibrated confidence interval.
- **Tomorrow's lunch:** no matching 2026-10-10 saved forecast exists; the advisor asks the manager to calculate one in Plan next meal and gives no invented quantity.
- **Ingredient expiry:** Tomatoes **12.00 kg raw stock**, reviewed for 2026-10-09, use-by 2026-10-10; Spinach **3.00 kg**, past an unclassified 2026-10-08 date and blocked; Paneer **5.00 kg**, unknown label/review and held from use. Source labels remain generated practice records.
- **NGO map:** **59 cached candidates** within **15 km**, with the recorded retrieval timestamp and actual directory links. No food acceptance is inferred; the current workspace has zero recorded acceptance declarations.
- **Plate waste:** human redistribution is always blocked; segregation and material-specific processor acceptance are required for supported non-human routes. No actual energy generation is invented.

## Executed verification

Before implementation: **131 backend tests passed** (12.09 s); frontend production build passed (5.92 s).

After implementation:

- **163 backend tests passed**, including **32 advisor tests**, in **15.61 s**. The original acceptance scenarios are included. One existing Starlette/httpx deprecation warning remains.
- `npm.cmd run typecheck`: passed.
- `npm.cmd run build`: passed; Vite built 2,190 modules in **6.39 s**. Advisor JS is **11.22 kB** (4.10 kB gzip), separately loaded; no bundle-size warning.
- Six running-backend checks returned HTTP 200: Groq saved forecast, Groq missing forecast, Gemini inventory, Groq NGO directory, Groq plate-waste safety and offline waste summary. All requested live AI cases returned `ai_assisted/provider_curated`.
- A complete SQLite `iterdump()` fingerprint before and after those six requests is identical. Unit tests also compare all database tables and directly verify SQLite rejects writes on the advisor read connection.
- Browser: actual Groq and Gemini requests, suggestions, typed input, Enter-to-send, loading state, evidence disclosure, eight historical rows in the existing evidence drawer, offline plate-waste answer, unconfigured OpenRouter fallback notice, conversation persistence across page navigation, New Chat, conflicting-context error and retry control. Final browser console error list was empty.
- Responsive widths **320, 768, 1024 and 1440 px**: no horizontal document overflow. Temporary viewport overrides were reset.

Automated cases cover exact saved forecast calculations; missing/stale/sparse snapshots; separate Rice/Dal forecasts; source labels; expired/unreviewed stock; review-date expiry; waste metrics and causal caveats; actual cached map entries and other locations; mandatory safety evidence; theoretical energy; absent Student Meal Pulse; empty data; unknown questions; no API key; sharing gate; all three provider wire contracts; malformed/invented model output; timeout; private-data exclusion; expired/stale/used recipient acceptances; read-only connection enforcement; invalid and excessive inputs; and existing regressions. Automated tests do not call real providers.

## Exact Windows commands

Backend terminal:

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack\frontend'
npm.cmd run dev
```

Open `http://127.0.0.1:5173/#advisor`. API docs: `http://127.0.0.1:8000/docs`. Already installed dependencies suffice; no new package was required.

Tests:

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
.\.venv\Scripts\python.exe -m pytest backend/tests -q --tb=short
.\.venv\Scripts\python.exe scripts\check_ai_providers.py
Set-Location frontend
npm.cmd run typecheck
npm.cmd run build
```

## Remaining limitations

OpenRouter is blocked by the supplied key's HTTP 401 and has no configured model. Student Meal Pulse is absent. The advisor retrieves saved forecasts and does not silently create or approve new ones. Topic/follow-up support is bounded to structured kitchen evidence; unsupported questions are explicitly declined. Responses are retained only for the current in-memory session and reflect the dataset version at answer time; send a new question after changing records. The directory is cached and incomplete; no recipient partnership or acceptance is implied. Existing generated practice data remains labeled and is not real measured KNSIT kitchen data. There is no public deployment, authentication, food-safety certification or independently verified energy production.
