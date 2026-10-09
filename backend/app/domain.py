import numpy as np
import pandas as pd
from .schemas import CHECKS
from . import research


def frame(rows):
    df = pd.DataFrame(rows)
    if not df.empty:
        df["served_kg"] = df.consumed_kg + df.plate_waste_kg
        df["weekday"] = pd.to_datetime(df.date).dt.day_name()
        df["waste_kg"] = df.untouched_surplus_kg + df.plate_waste_kg
    return df


def history_selection(df, target_date, meal, item, event):
    if df.empty:
        return df, "No historical records. Enter a manager-selected manual quantity."
    prior = df[(df.date < str(target_date)) & (df.meal == meal) & (df.item == item)].sort_values(["date", "record_id"])
    weekday = pd.Timestamp(target_date).day_name()
    matched = prior[(prior.weekday == weekday) & (prior.special_event == event)]
    if len(matched) >= 5:
        return matched.tail(8), None
    reason = f"Only {len(matched)} prior {weekday}/{event} records; using last 14 item/meal records across weekdays and events."
    return prior.tail(14), reason


def forecast_item(df, request, item, with_backtest=True):
    sample, fallback = history_selection(df, request.date, request.meal, item, request.special_event)
    base = {"item": item, "sample_count": len(sample), "fallback_reason": fallback,
            "history_ids": sample.record_id.tolist() if not sample.empty else [],
            "method": "Recency-weighted served kg per diner; weights 1..n", "status": "insufficient_data"}
    selected_rows = sample.to_dict("records") if not sample.empty else []
    base["data_quality"] = {
        "sources": sorted(set(r["source"] for r in selected_rows)),
        "confirmed_shortage_ids": [r["record_id"] for r in selected_rows if r.get("service_shortage_reported") is True],
        "shortage_unknown_count": sum(r.get("service_shortage_reported") not in [True, False] for r in selected_rows),
        "zero_surplus_ids": [r["record_id"] for r in selected_rows if r["untouched_surplus_kg"] <= 0.02],
        "caveat": "Served food includes plate waste. Confirmed shortages censor unmet demand; zero untouched surplus alone does not prove a shortage. Missing shortage flags are unknown, not no shortage."}
    if len(sample) >= 5:
        ratios = (sample.served_kg / sample.attendance).to_numpy(dtype=float)
        weights = np.arange(1, len(sample) + 1)
        demand = float(np.average(ratios, weights=weights) * request.expected_attendance)
        samples = ratios * request.expected_attendance
        base.update(status="ready", demand_kg=demand, recommended_kg=demand * (1 + request.buffer_pct / 100),
                    range_low_kg=float(np.percentile(samples, 10)), range_high_kg=float(np.percentile(samples, 90)),
                    range_label="Descriptive historical 10th–90th percentile; not a calibrated confidence interval",
                    demand_samples_kg=samples.tolist(), baseline_prepared_kg=float(sample.prepared_kg.mean()),
                    cost_per_kg=float(sample.cost_per_kg.mean()), served_per_diner_kg=float(np.average(ratios, weights=weights)),
                    simulator_max_kg=float(max(samples.max(), sample.prepared_kg.mean()) * 1.5))
    else:
        base["fallback_reason"] = f"Only {len(sample)} prior records; at least 5 required. Enter a manager-selected manual quantity."
    if with_backtest:
        base["backtest"] = backtest(df, request, item)
    return base


def backtest(df, request, item):
    errors, baseline_errors, evaluated = [], [], []
    if not df.empty:
        observations = df[(df.date < str(request.date)) & (df.meal == request.meal) & (df.item == item)].sort_values(["date", "record_id"]).tail(14)
        for row in observations.to_dict("records"):
            historical_request = request.model_copy(update={"date": row["date"], "expected_attendance": int(row["attendance"]), "special_event": row["special_event"]})
            predicted = forecast_item(df, historical_request, item, False)
            earlier = df[(df.date < row["date"]) & (df.meal == request.meal) & (df.item == item)]
            if predicted["status"] == "ready":
                baseline = float(earlier.served_kg.mean())
                errors.append(abs(predicted["demand_kg"] - row["served_kg"]))
                baseline_errors.append(abs(baseline - row["served_kg"]))
                evaluated.append({"record_id": row["record_id"], "date": row["date"], "actual_served_kg": row["served_kg"],
                                  "prediction_kg": predicted["demand_kg"], "baseline_kg": baseline,
                                  "range_low_kg": predicted["range_low_kg"], "range_high_kg": predicted["range_high_kg"],
                                  "training_ids": predicted["history_ids"]})
    return {"mae_kg": float(np.mean(errors)) if errors else None,
            "baseline_mae_kg": float(np.mean(baseline_errors)) if errors else None,
            "evaluation_count": len(errors), "attendance_known": True,
            "method": "Rolling last 14 prior observations; strictly earlier dates; actual attendance known. Baseline: earlier mean served kg.",
            "evaluations": evaluated,
            "range_diagnostics": {"coverage_pct": float(np.mean([r["range_low_kg"] <= r["actual_served_kg"] <= r["range_high_kg"] for r in evaluated]) * 100) if evaluated else None,
                                  "mean_width_kg": float(np.mean([r["range_high_kg"] - r["range_low_kg"] for r in evaluated])) if evaluated else None,
                                  "label": "Observed rolling coverage of descriptive historical 10–90% ranges; not conformal calibration or a guarantee."},
            "benchmark": research.benchmark(df, request, item, evaluated)}


def simulate(samples, quantity, baseline, cost, demand=None):
    samples = np.asarray(samples, dtype=float)
    def outcomes(q):
        return {"expected_surplus_kg": float(np.maximum(q - samples, 0).mean()),
                "expected_shortage_kg": float(np.maximum(samples - q, 0).mean()),
                "shortage_frequency": float((samples > q).mean())}
    candidate, original = outcomes(quantity), outcomes(baseline)
    point = float(samples.mean()) if demand is None else demand
    return {**candidate, "quantity_kg": quantity, "baseline_prepared_kg": baseline, "baseline": original,
            "point_surplus_kg": max(quantity - point, 0), "point_shortage_kg": max(point - quantity, 0),
            "prevented_untouched_surplus_kg": original["expected_surplus_kg"] - candidate["expected_surplus_kg"],
            "potential_cost_difference_inr": (baseline - quantity) * cost, "sample_count": len(samples),
            "label": "Projected from historical served demand; plate-waste prevention is not included."}


def review_state(batch):
    if batch["origin"] == "plate_waste":
        return "blocked", "Plate waste is always blocked from human redistribution."
    if batch["origin"] == "unknown":
        return "blocked", "Unknown origin; human redistribution blocked."
    checks = batch.get("checks", {})
    failed = [k for k in CHECKS if checks.get(k) is False]
    missing = [k for k in CHECKS if checks.get(k) is None]
    if failed:
        return "blocked", "Failed staff checks: " + ", ".join(failed)
    if missing or not batch.get("reviewer") or not batch.get("reviewed_at"):
        return "pending_review", "Documented review required: " + ", ".join(missing)
    return "eligible_pending_approval", "All staff attestations recorded; manager approval required. This is policy review, not food-safety certification."


def overview(rows):
    df = frame(rows)
    columns = ["prepared_kg", "consumed_kg", "served_kg", "untouched_surplus_kg", "plate_waste_kg", "waste_kg"]
    totals = {k: float(df[k].sum()) if not df.empty else 0 for k in columns}
    totals["estimated_waste_cost_inr"] = float((df.waste_kg * df.cost_per_kg).sum()) if not df.empty else 0
    totals["balance_difference_kg"] = totals["prepared_kg"] - totals["consumed_kg"] - totals["untouched_surplus_kg"] - totals["plate_waste_kg"]
    totals["untouched_pct"] = totals["untouched_surplus_kg"] / totals["prepared_kg"] * 100 if totals["prepared_kg"] else 0
    def aggregate(key):
        if df.empty:
            return []
        grouped = df.groupby(key)[columns].sum().reset_index()
        return grouped.to_dict("records")
    attendance = df.groupby(["date", "meal"]).attendance.max().sum() if not df.empty else 0
    return {"totals": totals, "daily": aggregate("date"), "weekday": aggregate("weekday"), "items": aggregate("item"),
            "record_count": len(rows), "meal_services": int(df.groupby(["date", "meal"]).ngroups) if not df.empty else 0,
            "diners": int(attendance), "sources": sorted(set(r["source"] for r in rows)),
            "date_from": str(df.date.min()) if not df.empty else None, "date_to": str(df.date.max()) if not df.empty else None}


def investigations(rows):
    df = frame(rows)
    if df.empty:
        return []
    findings = []
    for item, group in df.groupby("item"):
        ratios = group.plate_waste_kg / group.attendance
        untouched = group.untouched_surplus_kg / group.attendance
        findings.append({"id": "plate-" + item, "title": f"{item}: portion waste deserves its own intervention",
                         "observed_metrics": {"plate_waste_per_diner_kg": float(ratios.mean()),
                                              "untouched_per_diner_kg": float(untouched.mean()),
                                              "plate_share_of_served_pct": float(group.plate_waste_kg.sum() / group.served_kg.sum() * 100) if group.served_kg.sum() else 0},
                         "evidence_record_ids": group.record_id.tolist(), "sample_count": len(group),
                         "caveats": "Observed source-labeled pattern, not causal proof. Cooking less does not directly prevent plate waste.",
                         "suggested_action": "Trial smaller first servings with optional seconds; measure plate waste separately."})
        friday = group[group.weekday == "Friday"]
        other = group[group.weekday != "Friday"]
        if len(friday) >= 5 and len(other) >= 5:
            f = float((friday.untouched_surplus_kg / friday.attendance).mean())
            o = float((other.untouched_surplus_kg / other.attendance).mean())
            if f > o:
                findings.insert(0, {"id": "friday-" + item, "title": f"Friday {item.lower()} surplus is higher per diner",
                                   "observed_metrics": {"friday_untouched_per_diner_kg": f, "other_untouched_per_diner_kg": o,
                                                        "friday_mean_attendance": float(friday.attendance.mean()),
                                                        "other_mean_attendance": float(other.attendance.mean())},
                                   "evidence_record_ids": friday.record_id.tolist() + other.record_id.tolist(), "sample_count": len(group),
                                   "caveats": "Normalized comparison includes different events. Attendance differences are associations, not proven causes.",
                                   "suggested_action": "Use expected attendance to plan; inspect the shortage trade-off before approval."})
    return findings
