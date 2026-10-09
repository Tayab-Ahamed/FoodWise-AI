# Domain contracts
## Meal record
record_id unique string; date ISO YYYY-MM-DD; meal breakfast/lunch/dinner; item string; attendance integer >0 (actual diners); weekday derived from date; special_event none/exam/festival; prepared_kg, consumed_kg, untouched_surplus_kg, plate_waste_kg nonnegative cooked mass; cost_per_kg nonnegative estimated production cost per cooked kg; source synthetic/measured.
Derived served_kg = consumed_kg + plate_waste_kg.
Mass balance: prepared_kg = consumed_kg + untouched_surplus_kg + plate_waste_kg, tolerance 0.02 kg per row. Seed assumes no other losses. If real process losses are needed, introduce explicit other_loss_kg throughout contracts; never hide them in consumption.
Demand forecast targets served_kg (consumed plus plate waste), because food plated then discarded was still demanded at service. Predicting consumed alone risks shortages. Plate waste reduction requires a separate portion intervention; do not silently count it as prevented by cooking less.
Validate complete CSV atomically. Reject duplicate IDs, invalid dates, nonfinite values, negative quantities, unknown events, inconsistent mass balance; report row numbers. Max upload 5 MB/10000 rows. Existing IDs conflict; default reject. Preview and confirm before replacing active data. Store source label per dataset; uploads default user_provided_unverified, never automatically measured.
Quantities for chapati may have display_qty/display_unit=pieces and piece_weight_kg. Canonical mass remains kg. Inventory uses raw ingredient quantities separately.
## Inventory
batch_id, ingredient, quantity_kg, expiry_date, storage_verified bool, allergens list, source. Expired: expiry before selected date; due today: same date, review required; near expiry: next 2 days, configurable. Never infer safe storage from expiry date. Fixtures are illustrative label dates.
## Forecast
Filter by item+meal and dates strictly before target date. Estimate served kg per diner from last 8 matching weekday/event records, fallback last 14 matching item/meal records, minimum 5 valid records. Recency weights 1..n ordered oldest to newest. demand = expected_attendance * weighted mean(served_kg/attendance). Event match only if enough examples; show fallback reason.
Uncertainty: empirical 10th/90th percentiles of historical per-diner ratios times expected attendance; mark descriptive historical range, not calibrated confidence interval. No numeric confidence score masquerading as probability. With <5 rows return insufficient_data and an explicit manager-entered manual quantity.
Plan = demand * (1+buffer_pct/100), default buffer 5%, adjustable 0–20%. Round presentation to 0.1kg but calculate unrounded.
Rolling temporal evaluation: last 14 available item/meal observations, each predicted using earlier rows only and known actual attendance for evaluation. Baseline historical average served kg from earlier matching rows. Report MAE kg, evaluation count, method and whether attendance was known. Never claim universal superiority; show real results including regressions.
## Simulator
For quantity Q and demand samples Di = expected_attendance * historical served ratios:
expected_surplus = mean(max(Q-Di,0)); expected_shortage = mean(max(Di-Q,0)); empirical_shortage_frequency = count(Di>Q)/n.
At point demand D show surplus=max(Q-D,0), shortage=max(D-Q,0).
Potential preparation cost avoided = (baseline_prepared-Q)*cost_per_kg, can be negative; label negative as added cost. No promise of realized savings.
Compare baseline and candidate using same samples. Prevented untouched surplus estimate = baseline expected surplus - candidate expected surplus (can be negative). Do not count recovery as prevention or invent plate-waste reduction.
## Recovery
Batch origin untouched_surplus/plate_waste/unknown; quantity <= unallocated mass of linked record and category. Review fields: handling_log_complete, time_temperature_review_passed (staff attestation under local kitchen procedure), storage_verified, contamination_check_passed, label_allergen_info_present, reviewer, reviewed_at; each check true/false/null. No regulatory numeric threshold is hardcoded or claimed compliant. This prototype demonstrates a policy workflow, not certification. Production requires kitchen-approved policy and qualified review.
State: draft → pending_review → blocked OR eligible_pending_approval → approved_for_simulated_handoff → simulated_handoff_recorded.
plate_waste: always blocked for human redistribution, irrespective of override or prior state. unknown origin: blocked. Untouched with false/null checks: pending_review or blocked with reason, cannot approve. All checks true permits manager approval only. Approved status alone is not completed recovery.
Changing origin, quantity, linked record, checks or reviewer invalidates approval; re-evaluate server-side on every transition. Simulated handoff requires approved batch and partner demo flag. Repeated requests use idempotency keys; totals cannot exceed batch/category quantity. Compost/biogas route requires processor acceptance for material; otherwise “disposal review required”. No actual partner claims.
## Outcomes
Measured and projected panels separate. Approved plans may be compared with actual records, but no causal savings claim from one before/after observation. Record planning errors, per-diner waste and usage trends. Never add kg avoided, kg redistributed and kg composted into one “total saved” metric.
