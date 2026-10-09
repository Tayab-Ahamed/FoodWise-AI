# Three-minute FoodWise walkthrough

Start the backend and frontend using the [root README](../README.md). Use the generated practice workspace and planning date **2026-10-09**. The header's **?** opens the in-app guide. No API key or connection is needed for the core workflow.

## Before presenting

Use distinct actual-meal IDs for a fresh rehearsal. Existing allocations must not be overwritten or allocated twice. If you choose to reset, the topbar circular-arrow button requires explicit confirmation and clears the seeded practice workspace's decisions and logs. An operations workspace cannot be reset through this control.

## Present one food journey

| Time | Actions | Explain |
| --- | --- | --- |
| 0:00–0:25 | In **The big picture**, inspect Friday rice surplus and open its historical evidence. | Quantities come from backend accounting. The generated data demonstrates an association, not proven real-world savings. |
| 0:25–1:00 | In **Plan next meal**, use lunch, 160 expected diners, no event, and 5% buffer. Calculate, select Rice, vary the cooked quantity, inspect the temporal backtest, then save a manager-approved quantity. | Served demand includes plate waste. Reducing surplus must be balanced against shortage. A manager chooses the plan. |
| 1:00–1:30 | In **Record meal**, select the Rice plan. Record quantities that balance; for a 40.13 kg practice plan, use 34 consumed, 4.13 untouched, and 2 plate waste. Retain the generated source label and a unique actual ID. | This is an illustrative weighed-log scenario. The backend rejects mass-balance errors. If you selected a different plan quantity, enter a corresponding balanced scenario. |
| 1:30–2:20 | In **Recovery**, allocate the lunch's untouched quantity. Show the missing-evidence rejection, record all five handling checks, and obtain separate manager approval. In **Lunch → dinner**, explicitly load and save the generated holding example, check demand, enter a manual 20 kg dinner total when history is sparse, reserve the reviewed surplus, and obtain qualified approval. Log dinner against the resulting plan. | Untouched origin alone does not establish safety. Reviewed reuse reduces fresh preparation and retains the food's provenance. Manual dinner quantities are scenario assumptions, not invented forecasts. |
| 2:20–2:40 | Allocate lunch plate waste and attempt a human route. Demonstrate the backend block. If showing biogas, confirm segregation and an accepting practice processor before recording a simulated handoff. | Plate waste never enters human redistribution. Biogas is theoretical potential; no processor is contacted and no energy generation is measured. |
| 2:40–3:00 | In **Impact & evidence**, inspect reuse and simulated processing separately. Open **AI Kitchen Advisor** and ask what untouched surplus needs before reuse. | Evidence remains inspectable. Offline explanations work without keys; AI never approves food or dispatches it. |

For the dinner actual, an illustrative 20 kg service can be logged as 18 consumed, 1 untouched, and 1 plate waste. The approved reuse plan determines the fresh/reused split; never count transferred food as newly prepared twice.

## Optional demonstrations

- **Separate accounting fixture:** load the 100 kg fixture in Record meal. It balances as 82 consumed + 10 untouched + 8 plate waste; served food is 90 kg. It is a different item from Rice and must never replace forecast history.
- **CSV validation:** from the repository root, run `.\.venv\Scripts\python.exe scripts\make_demo_imports.py`. Upload `artifacts/invalid_history_upload.csv` to show row errors without mutation. The valid upload uses distinct IDs and commits only after preview and explicit confirmation.
- **Field station:** open the map around KNSIT and explicitly discover public-directory candidates. Pins do not establish partnerships or acceptance. Weather and live map services require a connection; cached snapshots are labeled. Outdoor weather is not holding-temperature evidence.
- **Connected AI:** configure a provider, then explicitly enable aggregate evidence sharing. The advisor prioritizes backend facts and falls back locally on errors. [AI guide](AI_KITCHEN_ADVISOR.md).
- **Expiry review:** on the overview, use the selected as-of date and inspect ingredient label, storage, condition, and staff-review requirements. Raw ingredient quantities are separate from cooked-food mass.

All practice records, holding examples, and handoffs remain labeled. Recovery review demonstrates policy and manager workflow; it is not food-safety certification.
