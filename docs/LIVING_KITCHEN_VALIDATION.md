# Living kitchen and KNSIT Field station

Implemented 2026-10-09 on top of the working P0, research and circular-kitchen extensions. Existing operating forms, forecasting algorithms, safety transitions and database schema are retained. No deployment, new dependency, autonomous agent or real recovery integration was added.

## Design and interaction

The overview is a living food landscape: a custom miniature campus-kitchen illustration, forest typography and selectable preparation, service, untouched-surplus and plate-waste streams. Selecting a stream reveals its explanation and opens the relevant existing workflow. Cooked mass comes directly from `/api/overview` and follows its date filters; it is an accounting view across meal services, not a combined savings metric. Recorded preparation may include reuse in multiple services; the circular ledger distinguishes newly prepared food.

The conceptual illustration is explicitly labeled and does not depict verified KNSIT kitchen, greenhouse, compost or biogas infrastructure. The locally bundled asset keeps the full experience available offline. Subtle motion has a pause/play control and reduced-motion CSS fallback. Food-stream buttons and the motion control have at least 44 px height. Horizontal navigation wraps into two rows on mobile instead of adding a sidebar. Existing meal planning, logs, manager decisions and evidence inspection remain connected.

The Field station adds:

- An approximate **KNS Institute of Technology** campus entrance point at latitude 13.086027, longitude 77.641252, from the institution's [published campus facilities document](https://knsit.com/wp-content/uploads/2024/05/7.1.1_Facilities_Provide_in_Campus.pdf). Its [official contact page](https://knsit.com/contact/) supports the Bengaluru address. This is not a surveyed kitchen location.
- An explicitly opened, interactive OpenStreetMap embed with contributor attribution, a larger-map link and an offline return control. It represents geographic context only; no invented NGOs, routes, acceptance or processor facilities.
- Explicitly fetched current Open-Meteo outdoor weather with source, provider time, retrieval time and live/cached/stale/unavailable states. It is a weather-model estimate, not a sensor measurement. Weather is never food-temperature evidence and never automatically modifies demand forecasts.
- City search and manual coordinates, validated on the backend. A location preference stays in this browser. Location changes clear old weather and map state; in-flight weather/search results are discarded if outdated.
- An inspectable evidence desk plus a system ledger distinguishing local demand models, deterministic rules, optional provider curation, SQLite persistence and human decisions.

## APIs and provider boundary

All new endpoints live under `/api/station`: `location`, `places`, `weather`, `systems`, and `brief`. These routes never write kitchen data or safety decisions.

The provider adapter uses installed `httpx` for documented REST requests, with fixed service hosts, no redirects and bounded timeouts. No model ID is guessed: the configured provider needs both a server key and an explicit JSON-capable model identifier. Root `.env` accepts simple assignments without executing or interpolating values; existing process environment wins. `.env` remains ignored. Keys never enter the frontend, URLs, returned configuration or errors.

Groq, Gemini and OpenRouter can select a short list of predefined evidence card IDs. **All displayed statements and numeric facts are authored by the server.** Free-form provider prose is never rendered. Unknown/duplicate IDs, extra fields, invalid JSON, missing responses, HTTP errors and timeouts use the deterministic offline briefing. Recovery briefings always retain the untouched-review and plate-waste block cards. No tools, actions, agents, safety approvals or automatic provider failover are used. Each external briefing requires explicit sharing of aggregate evidence; it sends no staff names, individual record IDs, CSVs or location.

Interfaces were checked against official documentation on 2026-10-09:

- [Groq compatibility](https://console.groq.com/docs/openai) and [structured outputs](https://console.groq.com/docs/structured-outputs): chat completions and JSON object mode.
- [Gemini generateContent](https://ai.google.dev/api/generate-content) and [structured output](https://ai.google.dev/gemini-api/docs/structured-output): `x-goog-api-key`, content parts and JSON response MIME type.
- [OpenRouter chat completion](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion) and [structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs).
- [Open-Meteo weather](https://open-meteo.com/en/docs) and [geocoding](https://open-meteo.com/en/docs/geocoding-api). Weather units, ranges, codes and observation freshness are validated. Memory cache: ten-minute fresh reuse, labeled stale fallback for up to one hour, maximum 128 locations. Stale data is never relabeled live.
- [OpenStreetMap embedding](https://wiki.openstreetmap.org/wiki/Export#Embeddable_HTML) and [tile usage policy](https://operations.osmfoundation.org/policies/tiles/). Uses the supported iframe, attribution and ordinary browser loading; no bulk tile download or offline tile cache.

## Files changed

New: `backend/app/station.py`, `backend/app/config.py`, `backend/tests/test_station.py`, `frontend/src/components/LivingLandscape.tsx`, `frontend/src/pages/StationPage.tsx`, `frontend/src/sustainability.css`, `frontend/public/foodwise-living-landscape.png`, `frontend/public/favicon.svg`, this document.

Updated: `backend/app/main.py` (configuration and router registration), `.env.example`, `frontend/src/App.tsx` (Field station navigation), `frontend/src/pages/OverviewPage.tsx`, `frontend/src/main.tsx`, `frontend/index.html`, `README.md`, `VALIDATION.md`, `docs/DEMO_WALKTHROUGH.md`.

No schema migration or reset is needed. Original source hash verification passed for all **14** files in the prior preservation manifest. The live database retains **274 records**, dataset version **8**, its completed reuse plan and two existing handoffs.

## Executed verification

Windows PowerShell:

```powershell
Set-Location 'C:\All Notes\FoodWise_AI_Codex_Pack'
.\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm.cmd run typecheck
npm.cmd run build
```

- New station tests: **26 passed**, covering offline totals, provider request contracts for all three providers, sharing requirements, no keys in status/URLs, invented or malformed output, mandatory safety evidence, timeouts, weather validation/cache/staleness/outages, coordinate bounds and geocoding fallback.
- Final complete regression suite: **112 passed in 9.16 seconds**, one existing Starlette/httpx TestClient deprecation warning. Includes the original P0 acceptance scenarios and research/circular-kitchen tests.
- Frontend type checking: passed.
- Final production build: passed (Vite 6.4.4, 2180 transformed modules, 5.08 seconds). Main JS 341.82 kB / 101.42 kB gzip; chart chunk 431.63 kB / 124.05 kB gzip; CSS 51.33 kB / 11.81 kB gzip. The full local illustration is copied into `dist`; no CDN asset is required.
- Backend restarted successfully at `http://127.0.0.1:8000`; Vite frontend running at `http://127.0.0.1:5173`.
- Browser: image loaded at its full native 1774 × 887 size; selectable plate-waste stream revealed the permanent redistribution block; pause control changed to play; navigation opened Field station.
- Browser: OpenStreetMap tiles and campus marker rendered. Current Open-Meteo weather returned **29.7 °C**, partly cloudy, precipitation **0.0 mm**, wind **9.7 km/h**, provider timestamp **9 Oct 2026 14:30 IST**, retrieved about **14:34 IST**. These are observations from verification, not hardcoded application values.
- Browser: real Bengaluru city search returned a result; selecting it persisted through reload; restore returned to the requested KNSIT point and cleared prior weather. Offline view remains available.
- Browser: selecting Groq required sharing confirmation; without configured keys the request returned an explicit offline fallback and the recovery briefing retained both mandatory safety cards.
- Responsive checks: overview and station at **320, 390, 768 and 1440 px** had document scroll width equal to client width (no horizontal overflow).
- Browser: recalculated the three-item lunch forecast and retained temporal backtest results; lowering Dal preparation to **15.0 kg** showed **4.5 kg expected shortage** and **100% empirical shortage frequency**, with the service trade-off warning. No new preparation approval or actual meal was saved. Final browser error log query returned an empty list.

Saved browser proofs: [overview](../artifacts/living-kitchen-overview.png) and [Field station with real map/weather and architecture ledger](../artifacts/living-kitchen-field-station.png). Temporary responsive viewport overrides were reset after verification.

Keyed production inference has **not** been performed: no real provider key is configured. Contract tests use mocked provider responses. Map availability depends on OpenStreetMap; cross-origin iframe tile failures cannot be reliably diagnosed by the host app, so the offline return and larger-map link remain visible. The illustrative landscape is a raster render with lightweight CSS motion and interactive overlays, not a WebGL model.

## Asset provenance

Generated with the built-in image-generation tool, inspected, and copied into the project at `frontend/public/foodwise-living-landscape.png` (2,998,937 bytes). It is local, conceptual artwork, not campus photography or operational evidence. No provider key was needed for generating this development asset.

Final image prompt:

> Use case: stylized-concept. Asset type: wide landscape illustration for FoodWise, a campus kitchen sustainability web application. Create a beautiful tactile miniature 3D diorama, isometric elevated perspective, on a pale sage green seamless background (#eef3e6). A small contemporary campus dining kitchen with open warm sunlit windows and flat terracotta roof occupies the left middle, a long communal outdoor dining table with small plates and chairs occupies the center, and a modest greenhouse, compost garden beds and closed biogas vessel occupy the right. Meandering pale walking paths connect the areas, surrounded by rich irregular trees, edible vegetable beds, tiny tomato plants, soft grasses. Handcrafted architectural model, natural wood, painted plaster, felt foliage, realistic soft afternoon shadows and delicate material texture, elegant museum installation, tasteful and inviting, not cartoon plastic or futuristic. Composition: broad horizontal floating landscaped island with generous breathing room at edges, all elements fully in frame. No text, no labels, no icons, no charts, no arrows, no logos, no watermarks, no people closeups. High quality art direction, warm daylight with a calm forest green and sage palette. This is a conceptual illustration, not a map or evidence of real facilities.
