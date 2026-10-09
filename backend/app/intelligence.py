"""A learned, offline planning coach. Forecasts served food, never safety.

Fixed ridge model; each backtest retrains on strictly earlier dates. Suggestions
remain separate from manager quantities and are not silently promoted by fit.
"""
import numpy as np
import pandas as pd
from fastapi import APIRouter
from pydantic import Field
from . import db, domain, research, station
from .schemas import StrictModel
from .errors import DomainError

router = APIRouter(prefix="/api/intelligence", tags=["Planning intelligence"])


class CoachRequest(StrictModel):
    forecast_id: str
    shortage_weight: float = Field(default=4, ge=1, le=20)
    use_groq: bool = False
    share_aggregate_evidence: bool = False


def learn(df, assumptions, item, shortage_weight):
    base = {"item": item, "status": "collect_history", "minimum_prior_services": 28}
    if df.empty:
        return {**base, "prior_service_count": 0, "message": "Record or import earlier services to train the AI model. Use a manager-selected quantity today."}
    prior = df[(df.date < assumptions["date"]) & (df.meal == assumptions["meal"]) & (df.item == item)].sort_values(["date", "record_id"])
    sources = sorted(set(prior.source))
    base.update(prior_service_count=len(prior), sources=sources)
    if len(prior) < 28:
        return {**base, "message": "The learned calendar model needs 28 earlier services. The standard forecast or manual plan remains available."}
    target = {"date": assumptions["date"], "attendance": assumptions["expected_attendance"], "special_event": assumptions["special_event"]}
    estimate, ids = research.calendar_prediction(prior, target)
    evaluations = []
    # Last fourteen dates; same-date rows can never train one another.
    for row in prior.tail(14).to_dict("records"):
        training = prior[prior.date < row["date"]]
        if len(training) < 28:
            continue
        predicted, training_ids = research.calendar_prediction(training, row)
        baseline = float((training.tail(14).served_kg/training.tail(14).attendance).mean()*row["attendance"])
        evaluations.append({"date": row["date"], "record_id": row["record_id"], "attendance": row["attendance"],
                            "actual_served_kg": row["served_kg"], "prediction_kg": predicted, "baseline_kg": baseline,
                            "training_ids": training_ids})
    if len(evaluations) < 5:
        return {**base, "status": "collect_validation", "message": "Model can fit, but needs five strictly temporal validation services before suggesting a quantity.",
                "training_ids": ids, "evaluation_count": len(evaluations)}
    # Scale out-of-sample residuals per diner to requested attendance. This is an
    # empirical error envelope, not a calibrated probability or confidence claim.
    residuals = np.array([(r["actual_served_kg"]-r["prediction_kg"])/r["attendance"] for r in evaluations])
    scenarios = np.maximum(0, estimate+residuals*assumptions["expected_attendance"])
    quantile = shortage_weight/(shortage_weight+1)
    recommendation = float(np.quantile(scenarios, quantile, method="higher"))
    actual = [r["actual_served_kg"] for r in evaluations]
    metrics = research.error_metrics(actual, [r["prediction_kg"] for r in evaluations])
    baseline = research.error_metrics(actual, [r["baseline_kg"] for r in evaluations])
    cost = float(prior.tail(14).cost_per_kg.mean())
    result = domain.simulate(scenarios, recommendation, float(prior.tail(14).prepared_kg.mean()), cost, estimate)
    shortage_count = sum(r.get("service_shortage_reported") is True for r in prior.tail(56).to_dict("records"))
    return {**base, "status": "ready", "recommendation_allowed": shortage_count == 0,
            "model": "Learned calendar ridge · NumPy", "model_version": "calendar-ridge-fixed-1-v1",
            "estimate_kg": estimate, "recommended_kg": recommendation, "range_low_kg": float(np.quantile(scenarios, .1)),
            "range_high_kg": float(np.quantile(scenarios, .9)), "shortage_weight": shortage_weight, "decision_quantile": quantile,
            "training_ids": ids, "training_service_count": len(ids), "trained_through": prior.date.max(),
            "evaluation_count": len(evaluations), "metrics": metrics, "baseline_metrics": baseline,
            "beats_recent_baseline": metrics["mae_kg"] < baseline["mae_kg"], "evaluations": evaluations,
            "scenario_outcomes": result,
            "shortage_reported_count": shortage_count,
            "range_label": "Empirical 10–90% residual scenario range; uncalibrated, no service-level guarantee",
            "message": "AI suggestion requires manager judgment. Stockouts can censor unmet demand. Generated training data cannot establish performance at KNSIT."}


@router.post("/prepare")
def prepare(request: CoachRequest):
    if request.use_groq and not request.share_aggregate_evidence:
        raise DomainError("sharing_required", "Confirm aggregate evidence sharing before using Groq.")
    with db.connect() as conn:
        snapshot = db.get(conn, "forecasts", request.forecast_id)
        if not snapshot:
            raise DomainError("not_found", "Forecast not found", 404)
        if snapshot["dataset_version"] != db.version(conn):
            raise DomainError("stale_forecast", "New observations are available; recalculate the forecast.", 409)
        results = [learn(domain.frame(db.records(conn)), snapshot["assumptions"], item, request.shortage_weight) for item in snapshot["assumptions"]["items"]]
    cards = []
    for index, item in enumerate(results):
        if item["status"] == "ready":
            text = (f"{item['item']}: learned served demand {item['estimate_kg']:.2f} kg; suggested preparation {item['recommended_kg']:.2f} kg. "
                    f"Temporal MAE {item['metrics']['mae_kg']:.2f} kg over {item['evaluation_count']} services. "
                    f"Recent-ratio baseline MAE {item['baseline_metrics']['mae_kg']:.2f} kg. "
                    f"Training sources: {', '.join(item['sources'])}. {item['message']}")
        else:
            text = f"{item['item']}: {item['message']}"
        cards.append({"id": f"dish_{index}", "title": item["item"], "text": text})
    selected, status = station.provider_selection("groq", cards, "preparation priorities: choose dishes requiring manager attention based on evidence") if request.use_groq else (None, "not_requested")
    result = {"id": db.identifier("coach"), "forecast_id": snapshot["id"], "dataset_version": snapshot["dataset_version"], "created_at": db.now(),
            "items": results, "ai_required": True, "local_model": "Calendar ridge trained from earlier served kg per diner",
            "groq_status": status, "briefing": [c for id in (selected or [c["id"] for c in cards][:3]) for c in cards if c["id"] == id],
            "decision_boundary": "AI proposes; the manager selects quantities. Food-safety review and recipient acceptance are independent server checks."}
    with db.connect(write=True) as conn:
        if db.version(conn) != snapshot["dataset_version"]:
            raise DomainError("stale_forecast", "Records changed during analysis; recalculate.", 409)
        db.put(conn, "coach_reports", result)
    return result
