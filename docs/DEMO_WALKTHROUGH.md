# Executable three-minute walkthrough

Keep backend and frontend running using the root README. Open http://127.0.0.1:5173. Reset using the topbar circular-arrow button and confirm **Reset synthetic demo** before rehearsal.

| Time | Exact actions | Explain |
|---|---|---|
| 0:00–0:35 | Overview → scroll to Friday rice finding → Inspect 90 records → close evidence | Synthetic history; cooked mass; normalized association, not causal discovery. |
| 0:35–1:20 | Plan next meal → Calculate forecast → Rice → change Quantity (kg) → inspect shortage and surplus → Demo manager → Approve preparation plan | Forecast targets served food, including plate waste. Descriptive range and temporal MAE come from prior history. Both service availability and surplus matter. |
| 1:20–1:45 | Record meal → Load 100 kg accounting fixture → Save actual meal | This is separate from forecast history: 100 prepared, 82 consumed, 10 untouched, 8 plate; backend shows 90 served. |
| 1:45–2:10 | Recovery → choose DEMO-100 → origin Plate waste → Allocate 8 → Create review batch → Request manager approval | The backend rejects human redistribution regardless of checks. Plate waste is its own intervention. |
| 2:10–2:40 | origin Untouched surplus → Allocate 10 → Create review batch → Request approval to show missing evidence → select Passed in all five reviews → Save documented review → Request manager approval → Record simulated handoff (use 5 kg) | Origin never certifies safety. Recorded checks and separate manager approval are necessary. No real partner booking happens. |
| 2:40–3:00 | Impact & evidence → inspect three distinct groups → Generate offline evidence report | Projected prevention, logged actuals and simulated recovery stay separate. The next step is a measured kitchen pilot. |

Optional quick checks: retry a handoff with identical fields for the same receipt; edit and save a review to clear approval; select unknown-acceptance compost processor to show disposition review required. Inventory expiry warnings are on Overview with the as-of date set to 2026-10-09.

For CSV rehearsal, run `scripts/make_demo_imports.py`. The generated invalid upload reports row errors without mutation. The generated valid upload uses new IDs and replaces only historical records after preview and explicit confirmation. Reset before judging to restore synthetic source labels and original evidence IDs.

For forecast feedback, log a Rice actual linked to an approved plan. Set a subsequent date with the matching weekday and recalculate. The mixed cooked accounting fixture is a different item, so it intentionally does not alter Rice forecasts.


## Connected circular kitchen demonstration (three minutes)

This extends the original P0 walkthrough. Use the same Windows launch commands in README. Data, temperature logs and handoffs in this scenario are explicitly synthetic/simulated. Do not reset the preserved database to present it. DEMO-100 and its completed outcomes are already retained from verification; inspect those, or use a new unique synthetic meal ID for a fresh rehearsal. Existing allocations must never be overwritten or allocated twice.

**0:00–0:25 — Account for lunch.** In Record meal, load the separate 100 kg fixture: 82 consumed, 10 untouched, 8 plate; backend balance is zero and served food is 90 kg. Save only if the ID is new. Explain that this one-row accounting example does not replace the 270-row forecast history.

**0:25–1:20 — Review before reuse.** In Recovery, select the recorded lunch and create a 10 kg untouched batch if it has not already been allocated. Unknown evidence blocks reuse. Mark the five synthetic checks passed, save the documented review and request manager batch approval. In Lunch → dinner, explicitly load the clearly synthetic holding example and save it. Show the procedure reference, separate container, monitoring attestations, 13:00–19:00 window and seven hourly 65 °C entries. Explain that this is a limited demo gate plus manager procedure review, not safety certification. Check dinner demand. With supplied lunch-only history, enter a **manual 20 kg** dinner total and confirm same-dish compatibility. Reserve 10 kg. Enter the demo manager name, attest qualification/procedure review and approve the revised plan: **10 fresh + 10 reused = 20 total**. The manual quantity is an illustrative scenario, not a validated portion or nutrition recommendation. Rejection releases the reservation; changed evidence invalidates unused approval.

**1:20–1:45 — Record the outcome.** In Record meal, select the newly approved reuse plan. Retain its synthetic source. Log 20 total food / 18 consumed / 1 untouched / 1 plate, 200 diners. The backend records 10 kg reused and 10 kg newly prepared. Future dinner forecasts can use its **19 kg served**, while one observation still requires manual fallback.

**1:45–2:20 — Keep plate waste out of human food.** Allocate lunch's 8 kg plate waste if it has not already been allocated. Attempt a human handoff: the backend rejects it permanently. In Biogas potential, confirm segregation and choose the accepting demo biogas processor. Review the editable assumptions, preview **0.800 m³ potential gas**, **1.670 kWh potential electricity**, **2.147 kWh potential useful heat**, then record the simulated handoff. No facility is contacted and no gas or electricity generation is recorded. A processor with unknown acceptance is blocked.

**2:20–2:45 — Show honest outcomes.** Impact & evidence shows **10 kg recorded reuse**, **8 kg simulated biogas allocation**, **3.817 kWh theoretical useful-energy potential**, and actual energy **not measured**. Reuse is a transfer between meals, not extra food or proven waste prevention. The existing forecast/simulator/backtest and offline reports remain available. Saved outcomes persist after restart.

**2:45–3:00 — Use ingredients deliberately.** In Overview, open ingredient eligibility. Review synthetic tomatoes as use-by, explicitly verify storage/condition, and supply staff/procedure references for 2026-10-09. At 200 recipe portions, Tomato rice uses **12 kg raw tomatoes** and shows **16 kg raw rice procurement shortage**. Tomato dal is an alternative using 8 kg tomatoes, not a simultaneous allocation. Expired spinach and unverified paneer are excluded. No raw-to-cooked yield or nutritional adequacy is invented.

For a short presentation, use the retained verified state for the two outcome sections and explain the review steps rather than creating duplicate records. The header's **?** guide also includes this connected scenario. Full checks and screenshots are in [CIRCULAR_KITCHEN_VALIDATION.md](CIRCULAR_KITCHEN_VALIDATION.md); assumptions, migration and exact files are in [CIRCULAR_KITCHEN_IMPLEMENTATION.md](CIRCULAR_KITCHEN_IMPLEMENTATION.md).
# Optional sustainability opening and closing

The original preparation → actuals → recovery sequence below remains the core demo. Replace its overview introduction with a short tour of the Living kitchen: select the **Serve** landscape stream to explain that demand includes plate waste, then **Separate plate waste** to show the backend redistribution boundary. The image is conceptual; figures are active-record accounting totals.

After the core workflow, open **Field station**. It centers on the approximate published entrance point for KNS Institute of Technology, Bengaluru. Choose **Open interactive map** and **Fetch local weather** to demonstrate optional live context, with timestamps and source attribution. Outdoor weather never establishes food safety or silently adjusts the forecast. Without internet, keep the local offline map view and evidence briefing.

At the evidence desk, select a topic and create an offline briefing. The system ledger explains local Pandas/NumPy models, deterministic safety rules, optional Groq/Gemini/OpenRouter evidence curation and manager decisions. No autonomous agent operates the kitchen. Provider keys and exact model IDs go only into root `.env`; without them, provider requests show the complete offline fallback. See [setup and limitations](LIVING_KITCHEN_VALIDATION.md).
