from datetime import date, timedelta
import numpy as np
import pytest
from backend.app import db, domain, research
from backend.app.schemas import ForecastRequest, OptimizationRequest, TrialRequest
from .test_acceptance import prediction, fixture, csv_bytes


def optimization(forecast_id="f", **changes):
    return {"forecast_id": forecast_id, "item": "Rice", "surplus_cost_per_kg": 45,
            "shortage_cost_per_kg": 180, "max_shortage_frequency": 1, "capacity_kg": 100, **changes}


def trial_input(**changes):
    return {"item": "Rice", "meal": "lunch", "baseline_start": "2026-07-11", "baseline_end": "2026-08-20",
            "trial_start": "2026-08-21", "trial_end": "2026-10-08", "record_scope": "history",
            "source_filter": "synthetic", "mode": "retrospective_comparison",
            "intervention": "smaller_first_serving_optional_seconds", "approved_by": "Manager", **changes}


def test_optimizer_matches_continuous_oracle_and_cost_monotonicity():
    samples = [8, 10, 10, 12, 20]
    quantities = []
    for underage in [1, 5, 10, 50, 100]:
        request = OptimizationRequest(**optimization(surplus_cost_per_kg=10, shortage_cost_per_kg=underage, capacity_kg=13.5))
        result = research.optimize(samples, request)
        q = result["selected"]["quantity_kg"]
        grid = np.linspace(0, 13.5, 2701)
        costs = [np.maximum(v - samples, 0).mean() * 10 + np.maximum(np.asarray(samples) - v, 0).mean() * underage for v in grid]
        assert result["selected"]["scenario_loss_inr"] <= min(costs) + 1e-9
        assert q <= 13.5
        quantities.append(q)
    assert quantities == sorted(quantities)


def test_optimizer_discrete_quantile_ties_and_zero_samples():
    r = research.optimize([10, 20], OptimizationRequest(**optimization(surplus_cost_per_kg=1, shortage_cost_per_kg=1)))
    assert r["unconstrained_quantity_kg"] == 10  # Any q in [10,20] minimizes; choose smallest.
    assert r["selected"]["quantity_kg"] == 10
    zero = research.optimize([0] * 5, OptimizationRequest(**optimization(capacity_kg=0, max_shortage_frequency=0)))
    assert zero["selected"]["quantity_kg"] == 0
    assert zero["selected"]["scenario_loss_inr"] == 0


def test_capacity_constraint_infeasible_then_feasible():
    request = OptimizationRequest(**optimization(capacity_kg=15, max_shortage_frequency=0))
    result = research.optimize([10, 20, 30, 40, 50], request)
    assert result["status"] == "capacity_infeasible" and result["selected"] is None
    assert result["capacity_best_effort"]["quantity_kg"] <= 15
    feasible = research.optimize([10, 20, 30, 40, 50], request.model_copy(update={"capacity_kg": 50}))
    assert feasible["selected"]["quantity_kg"] == 50
    assert feasible["selected"]["shortage_frequency"] == 0


def test_optimizer_api_persistence_approval_and_provenance(client):
    f = prediction(client)
    response = client.post("/api/optimize", json=optimization(f["id"], max_shortage_frequency=0))
    assert response.status_code == 200, response.text
    decision = response.json()
    assert decision["status"] == "ready"
    assert decision["history_ids"] == f["items"][0]["history_ids"]
    plan = {"forecast_id": f["id"], "quantities": {"Rice": decision["selected"]["quantity_kg"]},
            "approved_by": "Manager", "decision_ids": {"Rice": decision["id"]}}
    approved = client.post("/api/plans", json=plan)
    assert approved.status_code == 200
    evidence = client.post("/api/report", json={"forecast_id": f["id"], "plan_id": approved.json()["id"]}).json()
    assert evidence["evidence"]["optimization_decisions"]["Rice"]["assumptions"]["shortage_cost_per_kg"] == 180
    assert "not realized savings" in evidence["explanation"]
    assert client.post("/api/plans", json={**plan, "quantities": {"Rice": 1}}).json()["code"] == "decision_mismatch"
    assert client.post("/api/optimize", json=optimization(f["id"], capacity_kg=0, max_shortage_frequency=0)).json()["selected"] is None
    client.post("/api/actuals", json={"records": [fixture(client)]})
    assert client.post("/api/optimize", json=optimization(f["id"])).status_code == 409


@pytest.mark.parametrize("change", [{"shortage_cost_per_kg": 0}, {"surplus_cost_per_kg": -1},
                                   {"capacity_kg": -1}, {"max_shortage_frequency": 1.1}, {"capacity_kg": "NaN"}])
def test_optimization_invalid_inputs(client, change):
    f = prediction(client)
    assert client.post("/api/optimize", json=optimization(f["id"], **change)).status_code == 422


def test_confirmed_shortage_blocks_optimizer_and_unknown_remains_unknown(client):
    client.post("/api/actuals", json={"records": [fixture(client, record_id="SHORTAGE", item="Rice", date="2026-10-08", service_shortage_reported=True)]})
    f = prediction(client, date="2026-10-15")  # matched Thursday sample includes the shortage
    assert "SHORTAGE" in f["items"][0]["data_quality"]["confirmed_shortage_ids"]
    assert f["items"][0]["data_quality"]["shortage_unknown_count"] > 0
    blocked = client.post("/api/optimize", json=optimization(f["id"])).json()
    assert blocked["code"] == "censored_demand"
    assert blocked["details"][0]["field"] == "service_shortage_reported"
    assert "SHORTAGE" in blocked["details"][0]["message"]
    report = client.post("/api/report", json={"forecast_id": f["id"]}).json()
    assert "served food may understate desired demand" in report["explanation"]
    assert report["evidence"]["items"][0]["data_quality"]["confirmed_shortage_ids"] == ["SHORTAGE"]
    sparse = prediction(client, items=["Unknown dish"])
    assert client.post("/api/optimize", json=optimization(sparse["id"], item="Unknown dish")).json()["code"] == "insufficient_data"


def test_csv_optional_shortage_flag_legacy_and_empty(client):
    rows = [{**r, "record_id": "NEW-" + r["record_id"], "service_shortage_reported": ""} for r in db.load_csv(db.ROOT / "data/history_90_days.csv")]
    response = client.post("/api/datasets/preview", files={"file": ("history.csv", csv_bytes(rows), "text/csv")})
    assert response.json()["valid"]
    rows[0]["service_shortage_reported"] = True
    response = client.post("/api/datasets/preview", files={"file": ("history.csv", csv_bytes(rows), "text/csv")})
    assert response.json()["preview"][0]["service_shortage_reported"] is True


def test_temporal_models_metrics_and_range_coverage_have_no_leakage(client):
    f = prediction(client)
    bt = f["items"][0]["backtest"]
    benchmark = bt["benchmark"]
    rows = {r["record_id"]: r for r in client.get("/api/records").json()}
    assert all(m["evaluation_count"] == 14 for m in benchmark["models"])
    assert benchmark["default_model"] == "production"
    for e in benchmark["evaluations"]:
        for ids in e["training_ids"].values():
            assert all(rows[id]["date"] < e["date"] for id in ids)
    for model in benchmark["models"]:
        actual = np.asarray([e["actual_served_kg"] for e in benchmark["evaluations"]])
        pred = np.asarray([e["predictions"][model["key"]] for e in benchmark["evaluations"]])
        assert model["mae_kg"] == pytest.approx(abs(pred - actual).mean())
        assert model["bias_kg"] == pytest.approx((pred - actual).mean())
        assert model["rmse_kg"] == pytest.approx(np.sqrt(((pred - actual) ** 2).mean()))
        assert model["wape_pct"] == pytest.approx(abs(pred - actual).sum() / actual.sum() * 100)
    coverage = np.mean([e["range_low_kg"] <= e["actual_served_kg"] <= e["range_high_kg"] for e in bt["evaluations"]]) * 100
    assert bt["range_diagnostics"]["coverage_pct"] == pytest.approx(coverage)
    # Appending a later observation must not change a historical benchmark.
    client.post("/api/actuals", json={"records": [fixture(client, record_id="FUTURE", item="Rice", date="2027-01-01")]})
    assert prediction(client)["items"][0]["backtest"] == bt


def test_sparse_benchmark_never_fabricates_metrics(client):
    f = prediction(client, date="2026-07-13")
    assert all(m["status"] == "insufficient_data" and m["mae_kg"] is None for m in f["items"][0]["backtest"]["benchmark"]["models"])


def test_trial_weighted_observations_sources_duplicates_and_insufficient():
    t = TrialRequest(**trial_input(record_scope="actual")).model_dump(mode="json")
    rows = []
    for start, plate in [(date(2026, 7, 11), 1), (date(2026, 8, 21), 0.5)]:
        for day in range(5):
            diners = 10 + day * 10
            rows.append({"record_id": f"{start}-{day}", "date": str(start + timedelta(days=day)), "item": "Rice", "meal": "lunch", "special_event": "none",
                         "attendance": diners, "source": "synthetic", "plate_waste_kg": plate, "consumed_kg": 8, "untouched_surplus_kg": 2})
    r = research.trial_evaluation(rows, t)
    assert r["status"] == "comparison_available"
    assert r["baseline"]["per_diner_g"]["plate_waste_kg"] == pytest.approx(5 / 150 * 1000)
    assert r["change_per_diner_g"]["plate_waste_kg"] == pytest.approx(-2.5 / 150 * 1000)
    assert r["baseline"]["shortage_unknown_count"] == 5
    duplicate = research.trial_evaluation(rows + [{**rows[0], "record_id": "DUP"}], t)
    assert duplicate["status"] == "collect_more_services" and duplicate["change_per_diner_g"] is None
    assert set(duplicate["excluded_duplicate_ids"]) == {rows[0]["record_id"], "DUP"}
    measured = research.trial_evaluation(rows, {**t, "source_filter": "measured"})
    assert measured["baseline"]["services"] == 0 and measured["change_per_diner_g"] is None


def test_trial_api_persists_actual_scope_and_reset(client):
    response = client.post("/api/trials", json=trial_input())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "comparison_available"
    assert result["baseline"]["sources"] == ["synthetic"]
    assert client.get("/api/trials").json()[0]["trial"]["id"] == result["trial"]["id"]
    empty = client.post("/api/trials", json=trial_input(record_scope="actual")).json()
    assert empty["status"] == "collect_more_services" and empty["change_per_diner_g"] is None
    assert client.post("/api/trials", json=trial_input(mode="planned_trial")).json()["code"] == "trial_scope"
    assert client.post("/api/trials", json=trial_input(record_scope="actual", mode="planned_trial")).json()["code"] == "past_trial"
    assert client.post("/api/trials", json=trial_input(trial_start="2026-08-20")).status_code == 422
    client.post("/api/demo/reset", json={"confirm": "RESET SYNTHETIC DEMO"})
    assert client.get("/api/trials").json() == []
    with db.connect() as conn:
        assert db.all_objects(conn, "decisions") == []
