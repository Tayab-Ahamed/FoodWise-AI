"""Reproducible exploratory results using only the preserved synthetic history."""
import json
from backend.app import db, domain, research
from backend.app.schemas import ForecastRequest, OptimizationRequest


def main():
    rows = db.load_csv(db.ROOT / "data" / "history_90_days.csv")
    request = ForecastRequest(date="2026-10-09", meal="lunch", expected_attendance=160,
                              special_event="none", buffer_pct=5, items=["Rice", "Dal", "Vegetable Curry"])
    df = domain.frame(rows)
    results = {"source": "Preserved synthetic 90-day history; accounting fixture excluded", "assumptions": request.model_dump(mode="json"), "items": []}
    for name in request.items:
        item = domain.forecast_item(df, request, name)
        costs = OptimizationRequest(forecast_id="experiment", item=name, surplus_cost_per_kg=item["cost_per_kg"],
                                    shortage_cost_per_kg=180, max_shortage_frequency=0.2, capacity_kg=item["simulator_max_kg"])
        policy = research.optimize(item["demand_samples_kg"], costs)
        results["items"].append({"item": name, "demand_kg": item["demand_kg"], "sample_count": item["sample_count"],
                                 "data_quality": item["data_quality"], "benchmark": item["backtest"]["benchmark"]["models"],
                                 "range_diagnostics": item["backtest"]["range_diagnostics"],
                                 "cost_assumptions": costs.model_dump(), "optimization": {k: policy[k] for k in ["status", "critical_ratio", "selected"]}})
    path = db.ROOT / "docs" / "research_results.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
