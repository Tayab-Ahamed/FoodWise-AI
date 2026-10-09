"""Transparent, offline methods inspired by the cited research register.

No upstream code is imported. Inputs are validated by the API schemas; all
quantities are cooked kg. Benchmarks never change the production predictor.
"""
import numpy as np
import pandas as pd
from collections import Counter


def error_metrics(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if not len(actual):
        return {"mae_kg": None, "rmse_kg": None, "bias_kg": None, "wape_pct": None, "evaluation_count": 0}
    error = predicted - actual
    return {"mae_kg": float(np.abs(error).mean()), "rmse_kg": float(np.sqrt((error ** 2).mean())),
            "bias_kg": float(error.mean()),
            "wape_pct": float(np.abs(error).sum() / actual.sum() * 100) if actual.sum() else None,
            "evaluation_count": len(actual)}


def calendar_prediction(prior, row):
    # Fixed regularization and a bounded trend. No hyperparameter search on holdout.
    train = prior.tail(56)
    first = pd.Timestamp(train.date.min())
    span = max((pd.Timestamp(train.date.max()) - first).days, 1)

    def features(r):
        d = pd.Timestamp(r["date"])
        trend = min(max((d - first).days / span, 0), 1)
        return [1, trend, *[float(d.weekday() == i) for i in range(1, 7)],
                float(r["special_event"] == "exam"), float(r["special_event"] == "festival")]

    x = np.asarray([features(r) for r in train.to_dict("records")])
    y = (train.served_kg / train.attendance).to_numpy(dtype=float)
    penalty = np.diag([0] + [1] * (x.shape[1] - 1))
    coefficients = np.linalg.solve(x.T @ x + penalty, x.T @ y)
    estimate = max(float(np.asarray(features(row)) @ coefficients), 0) * row["attendance"]
    return estimate, train.record_id.tolist()


def benchmark(df, request, item, evaluations):
    names = {"production": "P0 recency-weighted served/diner", "mean": "Earlier mean served kg",
             "recent": "Recent 14 served/diner mean", "seasonal": "Latest same-weekday served/diner",
             "calendar": "Experimental calendar ridge (fixed penalty 1)"}
    results = []
    for evaluation in evaluations:
        date = evaluation["date"]
        row = df[df.record_id == evaluation["record_id"]].iloc[0].to_dict()
        prior = df[(df.date < date) & (df.meal == request.meal) & (df.item == item)].sort_values(["date", "record_id"])
        recent = prior.tail(14)
        matched = prior[prior.weekday == pd.Timestamp(date).day_name()]
        seasonal = matched.tail(1) if len(matched) else prior.tail(1)
        predictions = {"production": evaluation["prediction_kg"], "mean": evaluation["baseline_kg"],
                       "recent": float((recent.served_kg / recent.attendance).mean() * row["attendance"]),
                       "seasonal": float((seasonal.served_kg / seasonal.attendance).iloc[0] * row["attendance"])}
        ids = {"production": evaluation["training_ids"], "mean": prior.record_id.tolist(),
               "recent": recent.record_id.tolist(), "seasonal": seasonal.record_id.tolist()}
        if len(prior) >= 28:
            predictions["calendar"], ids["calendar"] = calendar_prediction(prior, row)
        results.append({"record_id": row["record_id"], "date": date, "attendance": row["attendance"],
                        "actual_served_kg": row["served_kg"], "predictions": predictions, "training_ids": ids,
                        "shortage_reported": row.get("service_shortage_reported") is True})
    # Calendar is included only if available on every shared evaluation service.
    models = []
    for key, label in names.items():
        complete = bool(results) and all(key in r["predictions"] for r in results)
        metrics = error_metrics([r["actual_served_kg"] for r in results] if complete else [],
                                [r["predictions"][key] for r in results] if complete else [])
        models.append({"key": key, "label": label, "status": "compared" if complete else "insufficient_data", **metrics})
    return {"models": models, "evaluations": results, "default_model": "production",
            "method": "Same last 14 eligible services; strictly earlier dates; actual attendance known. Calendar needs 28 prior observations on every service. Bias = predicted minus served.",
            "caveat": "Exploratory comparison on source-labeled observations, not independent model selection or real-kitchen validation. Stockouts may censor latent demand."}


def optimize(samples, request):
    samples = np.asarray(samples, dtype=float)

    def outcome(q):
        surplus = float(np.maximum(q - samples, 0).mean())
        shortage = float(np.maximum(samples - q, 0).mean())
        frequency = float((samples > q).mean())
        return {"quantity_kg": float(q), "expected_surplus_kg": surplus, "expected_shortage_kg": shortage,
                "shortage_frequency": frequency,
                "scenario_loss_inr": surplus * request.surplus_cost_per_kg + shortage * request.shortage_cost_per_kg,
                "service_constraint_met": frequency <= request.max_shortage_frequency + 1e-12}

    rho = request.shortage_cost_per_kg / (request.shortage_cost_per_kg + request.surplus_cost_per_kg)
    unconstrained = float(np.quantile(samples, rho, method="inverted_cdf"))
    # Piecewise linear empirical loss reaches its minimum at a demand knot or
    # boundary. Include capacity even when it lies between demand observations.
    grid = sorted(set([0.0, float(request.capacity_kg), *[float(s) for s in samples if s <= request.capacity_kg]]))
    frontier = [outcome(q) for q in grid]
    feasible = [r for r in frontier if r["service_constraint_met"]]
    selected = min(feasible, key=lambda r: (r["scenario_loss_inr"], r["quantity_kg"])) if feasible else None
    best_at_capacity = min(frontier, key=lambda r: (r["scenario_loss_inr"], r["quantity_kg"]))
    return {"status": "ready" if selected else "capacity_infeasible", "critical_ratio": rho,
            "unconstrained_quantity_kg": unconstrained, "selected": selected, "capacity_best_effort": best_at_capacity,
            "frontier": frontier, "sample_count": len(samples),
            "frequency_resolution": 1 / len(samples),
            "method": "Empirical newsvendor: minimize mean surplus × overage cost + mean shortage × underage cost, constrained by capacity and observed shortage frequency.",
            "caveat": "Projected scenario loss uses manager-specified penalties, not realized savings. Samples are equally weighted historical served demand at expected attendance, not a guaranteed future demand distribution."}


def trial_evaluation(rows, trial):
    matches = [r for r in rows if r["item"] == trial["item"] and r["meal"] == trial["meal"]
               and (trial["source_filter"] == "all" or r["source"] == trial["source_filter"])]
    duplicate_dates = {d for d, count in Counter(r["date"] for r in matches).items() if count > 1}
    excluded_ids = [r["record_id"] for r in matches if r["date"] in duplicate_dates
                    and trial["baseline_start"] <= r["date"] <= trial["trial_end"]]

    def phase(start, end):
        group = [r for r in matches if start <= r["date"] <= end and r["date"] not in duplicate_dates]
        diners = sum(r["attendance"] for r in group)
        total = {k: sum(r[k] for r in group) for k in ["plate_waste_kg", "untouched_surplus_kg", "consumed_kg"]}
        total["served_kg"] = total["consumed_kg"] + total["plate_waste_kg"]
        return {"services": len(group), "diners": diners, "totals": total,
                "per_diner_g": {k: v / diners * 1000 if diners else None for k, v in total.items()},
                "evidence_ids": [r["record_id"] for r in group], "sources": sorted(set(r["source"] for r in group)),
                "event_counts": {e: sum(r["special_event"] == e for r in group) for e in ["none", "exam", "festival"]},
                "shortage_reported_count": sum(r.get("service_shortage_reported") is True for r in group),
                "shortage_unknown_count": sum(r.get("service_shortage_reported") is None for r in group)}

    before = phase(trial["baseline_start"], trial["baseline_end"])
    after = phase(trial["trial_start"], trial["trial_end"])
    ready = min(before["services"], after["services"]) >= 5
    difference = {k: after["per_diner_g"][k] - before["per_diner_g"][k] for k in before["totals"]} if ready else None
    return {"trial": trial, "baseline": before, "comparison": after, "status": "comparison_available" if ready else "collect_more_services",
            "minimum_services_per_phase": 5, "change_per_diner_g": difference, "excluded_duplicate_ids": excluded_ids,
            "label": "Observed comparison; retrospective mode does not establish that an intervention occurred.",
            "caveat": "Attendance-weighted totals per diner; no causal savings, nutrition adequacy, or statistical significance claim. Dates, menus, events, self-reported actions and source mix may confound differences. Optional seconds must remain available."}
