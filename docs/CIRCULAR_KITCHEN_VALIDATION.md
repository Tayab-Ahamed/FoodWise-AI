# Executed extension verification — 9 October 2026

## Baseline and final checks

| Check actually executed | Before changes | Final result |
|---|---|---|
| `.\.venv\Scripts\python.exe -m pytest backend/tests -q --tb=short` | **45 passed**, 18.26 s | **86 passed**, **22.00 s**, 0 failed |
| `npm.cmd run typecheck` in `frontend` | Passed | Passed, exit 0 |
| `npm.cmd run build` in `frontend` | Passed, 29.34 s | Passed, Vite 6.4.4, **2,178 modules**, **9.58 s** |
| Final build output | Existing working bundles | CSS 34.85 kB; main JS 319.94 kB / gzip 95.27; chart JS 449.84 kB / gzip 128.31 |
| Local backend | Existing running app | Restarted with final implementation; health `ok`, dataset version **8**, port **8000** |
| Local frontend | Existing running app | Port **5173**, final HTTP **200**, browser workflow exercised |
| Data preservation | Live database backed up before edits | Every pre-existing ID retained; original JSON payloads retained; inventory annotations added without changing original fields; **14/14** supplied data/spec file hashes unchanged |

There were **no baseline test, type or build failures**. During implementation, duplicate frontend declarations were caught and removed before the successful builds. One new recipe test incorrectly assumed inventory row ordering after SQLite `INSERT OR REPLACE`; it was fixed to assert the intended batch ID. No tests were removed. The final suite has 41 additional collected cases beyond the original 45. The one non-failing Starlette TestClient/httpx deprecation warning existed at baseline and remains. Windows sandbox socket/build restrictions were handled by executing the same checks in the approved local host environment; they were not reported as application failures.

Feature A/B verification gate was completed **before** Feature C implementation: **72 passed**, frontend type/build passed, and the connected lunch, dinner and biogas browser workflow succeeded. Later accounting and inventory cases raised the complete suite to 86.

## New meaningful domain coverage

- Missing/unknown/failed handling evidence, unsupported holding mode, missing timezone, date/window errors, insufficient or unsafe temperature logs: reuse blocked.
- Current base review and separate manager approval required; qualified-manager and applicable-procedure attestations required for the revised dinner plan.
- Permanent plate-waste block in both human redistribution and dinner reuse, including attempts with all five handling checks passed.
- No reservation beyond batch remainder or total dinner food; prior handoffs reduce availability; reservations reduce human/processor handoff availability.
- Concurrent reservations are serialized; rejection releases mass. Unknown-origin allocations share the total pool and block reuse.
- Changed handling evidence, failed base reviews and renewed batch approvals invalidate unused approvals. Invalidated plans cannot record dinner use. Completed outcomes remain immutable and continue to debit the ledger.
- Synthetic source retention, fresh/reuse provenance, one linked actual outcome, database restart persistence, served-food feedback, offline reuse explanation, reset coverage.
- Biogas arithmetic checked against independent expected quantities, immutable assumption snapshots, efficiency conservation, invalid yield, missing segregation, unsupported processors, receipt retries and changed-assumption conflicts. Actual energy remains null.
- Legacy inventory cannot silently become eligible; review date, label type, condition and storage checks; use-by/best-before distinction; expired/unsafe stock excluded; scaled raw requirements and procurement shortages; multiple-batch date ordering; capped usage; no inventory consumption by recipe viewing; persistence, audit and explicit demo reset.
- All original forecasting, temporal backtesting, import, accounting, recovery, optimization and portion-trial acceptance tests still pass.

## Connected browser demonstration actually executed

Using the existing in-app browser against the user's preserved database, without resetting it:

1. Loaded and saved the separate **DEMO-100** synthetic lunch actual: **100 prepared / 82 consumed / 10 untouched / 8 plate waste**, **90 kg served**, 200 diners.
2. Allocated its **10 kg untouched** batch. Recorded all five passed synthetic attestations and requested batch-manager approval.
3. Explicitly loaded the synthetic hot-holding example: 13:00–19:00, seven hourly 65 °C readings, procedure/container/monitoring attestations. Saved detailed evidence.
4. Checked dinner demand. The UI correctly reported insufficient dinner history and required a manual target. Entered **20 kg total**, reserved **10 kg**, attested same-dish compatibility and qualified-manager/procedure review, and approved **10 kg fresh + 10 kg reused**. Saved plan: `plan-8a5b4c123b984c38`.
5. Logged the linked synthetic dinner actual `ACT-ea9122da`: **20 total / 18 consumed / 1 untouched / 1 plate**, **19 kg served**. The backend recorded **10 reused + 10 fresh** and completed the allocation.
6. Allocated lunch's **8 kg plate-waste** batch. Attempted a human handoff: the backend rejection was displayed: **“Plate waste is always blocked from human redistribution.”**
7. Confirmed segregation, previewed the default biogas scenario, and saved an **8 kg simulated** accepted-processor handoff. The UI displayed **0.800 m³ potential biogas**, **1.670 kWh potential electricity**, **2.147 kWh potential useful heat**. No energy generation was claimed.
8. Impact displayed **10 kg recorded reuse**, **8 kg simulated biogas**, **3.817 kWh theoretical useful potential**, and actual energy **not measured**. After backend restart the same outcomes persisted. Gross actual service food is **181 kg**, newly prepared actual mass **171 kg**; these totals include the two pre-existing actual meal logs.
9. Checked a **2026-10-11 dinner** forecast for Mixed cooked meal. It included **one earlier dinner observation** and honestly retained manual fallback because five are required. Lunch history was not borrowed. The exact 19 kg served feedback is also asserted by backend tests.
10. Opened Overview ingredient review. Before review, no recipes were eligible. Explicitly reviewed **synthetic INV-1 tomatoes** as use-by, passed storage/condition, and supplied staff/procedure references. At **200 portions**, Tomato rice showed **12 kg tomatoes required / 12 available / 12 used / 0 shortage**, and **16 kg rice procurement shortage**. Tomato dal was a separate alternative using **8 kg tomatoes**. Expired spinach and unverified paneer remained excluded.
11. Revisited recovery and confirmed the saved holding reviewer/log loaded from persisted evidence. Responsive checks for **320, 390, 768 and 1440 px** on both recovery and recipe views showed document client width equal to scroll width after layout settled. Wide ingredient tables scroll inside their containers. Temporary viewport overrides were reset.
12. Final browser error-log query returned **[]**. Expected domain rejections appeared as application alerts. Local HTTP checks returned backend health `ok` and frontend `200`.

Screenshots: [circular outcomes](../artifacts/circular-impact-browser.jpg), [recipe quantities](../artifacts/circular-recipes-browser.jpg). The connected synthetic demo state is intentionally retained for review. No existing rows were deleted or reset.

## Remaining limits

Reuse supports same-day hot holding and identical cooked dishes only; it does not validate chilling, reheating, transformations, regulatory compliance or food safety. Manager qualification, logs and measurements are staff attestations. Sparse dinner history requires a manual quantity with no invented uncertainty or nutritional adequacy claim. Recipe bills are illustrative, raw-only alternatives, not reservations or cooked-yield/nutrition plans. Every processor is an explicitly simulated demo record; gas/energy figures use editable assumptions and no measured energy outcome exists. The original TestClient deprecation warning remains non-failing. There are no unresolved application test/type/build failures from this extension.
