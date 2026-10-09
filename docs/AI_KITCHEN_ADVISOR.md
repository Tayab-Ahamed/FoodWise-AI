# AI Kitchen Advisor

The advisor is a read-only view of validated kitchen evidence. Open **AI Kitchen Advisor** in the main navigation or visit `http://127.0.0.1:5173/#advisor` after starting the application.

## What uses AI

- **Local prediction:** the NumPy prep coach learns served kg per diner from earlier services, calendar features, and declared events. It exposes rolling model errors and a recent baseline, and works offline.
- **Connected evidence curation:** Groq (default) or Gemini prioritizes server-authored evidence cards. The shared provider adapter also supports OpenRouter in Field station.
- **Offline explanations:** deterministic evidence selection remains available when a provider is unavailable or sharing is disabled.

The advisor reads saved forecasts, inventory eligibility, waste findings, recovery policy, recorded recipient acceptance, and cached public-directory listings. It does not create forecasts or invent missing quantities. Calculate a forecast in **Plan next meal** before asking about a specific preparation date.

## Configure a provider

From the repository root in PowerShell, create `.env` only if it does not already exist:

```powershell
if (!(Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
notepad .env
```

Set the provider's API key and an exact JSON-capable model identifier available to your account, then restart the backend. See [.env.example](../.env.example) for variable names. Never put credentials in frontend code or `VITE_` variables. Configuration status does not prove a provider request will succeed.

In the advisor, choose Groq or Gemini and explicitly enable aggregate evidence sharing. Use **Offline** without sharing for a completely local response. The opt-in diagnostic `scripts/check_ai_providers.py` makes real provider requests using configured credentials; it is not part of the offline test suite.

## Evidence and privacy boundary

The backend calculates every displayed fact and number. A provider can select a small set of temporary evidence aliases; unknown aliases, duplicate choices, extra prose, invalid JSON, timeouts, and upstream failures trigger the local fallback. Required safety and forecast context is retained regardless of model selection.

Raw questions, chat history, staff names, private review notes, internal record IDs, and coordinates are not sent to a provider. Recognized topics, public-directory facts, and aggregate kitchen evidence may be shared after consent. Conversation history stays in browser memory, up to 24 turns; **New Chat** or a full reload clears it.

AI cannot change food quantities, approve preparation or recovery, override the plate-waste block, contact recipients, or execute a handoff. A nearby organization is a candidate, not recipient acceptance. The advisor is not an autonomous agent or unrestricted general-purpose chatbot.

## API

- `GET /api/advisor/capabilities`: supported providers and current configuration status, without credentials.
- `POST /api/advisor/chat`: validated question and optional planning context, returning evidence-backed text, source labels, reference IDs, dataset version, and limitations.

Example local-only request:

```json
{
  "question": "What can we do with untouched surplus?",
  "provider": "offline",
  "share_aggregate_evidence": false,
  "history": [],
  "planning_date": null,
  "meal": null
}
```

Questions are limited to 1,000 characters. Missing, stale, or sparse forecast evidence is reported explicitly. History-derived ranges are descriptive, not calibrated guarantees. Send a new question after changing kitchen records to obtain a current snapshot.

Use the running [OpenAPI documentation](http://127.0.0.1:8000/docs) for complete request and response contracts. The isolated regression suite includes 32 advisor cases: validation, evidence provenance, privacy, provider failure, and safety boundaries. [Verification](PUBLISH_VALIDATION.md).
