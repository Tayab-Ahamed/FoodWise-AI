import csv
import io
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import db, domain
from backend.app.main import app
from backend.app.schemas import CHECKS, ForecastRequest, Record

DATA = Path(__file__).resolve().parents[2] / "data"


def prediction(client, **changes):
    response = client.post("/api/forecast", json={"date": "2026-10-09", "meal": "lunch", "expected_attendance": 160,
                                               "special_event": "none", "buffer_pct": 5, "items": ["Rice"], **changes})
    assert response.status_code == 200, response.text
    return response.json()


def fixture(client, **changes):
    return {**client.get("/api/demo/accounting").json(), **changes}


def log_fixture(client):
    result = client.post("/api/actuals", json={"records": [fixture(client)]})
    assert result.status_code == 200, result.text
    return result.json()


def batch(client, origin="untouched_surplus", amount=10):
    response = client.post("/api/recovery/batches", json={"record_id": "DEMO-100", "origin": origin, "quantity_kg": amount})
    assert response.status_code == 200, response.text
    return response.json()


def review(client, id, **changes):
    return client.patch(f"/api/recovery/batches/{id}/review", json={**{k: True for k in CHECKS}, "reviewer": "Staff", **changes})


def approve(client, id):
    return client.post(f"/api/recovery/batches/{id}/approve", json={"approved_by": "Manager"})


def handoff(client, id, key="handoff-1", amount=5, route="human_redistribution", partner="demo-community"):
    return client.post(f"/api/recovery/batches/{id}/handoff", json={"route": route, "partner_id": partner, "quantity_kg": amount, "idempotency_key": key})


def csv_bytes(rows):
    output = io.StringIO()
    fields = [k for k, v in rows[0].items() if v is not None]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def preview(client, rows):
    return client.post("/api/datasets/preview", files={"file": ("history.csv", csv_bytes(rows), "text/csv")})


def test_seed_mass_accounting_and_separate_fixture(client):
    result = client.get("/api/overview").json()
    assert result["record_count"] == 270
    assert result["sources"] == ["synthetic"]
    totals = result["totals"]
    assert totals["served_kg"] == pytest.approx(totals["consumed_kg"] + totals["plate_waste_kg"])
    for r in client.get("/api/records").json():
        assert abs(r["prepared_kg"] - r["consumed_kg"] - r["untouched_surplus_kg"] - r["plate_waste_kg"]) <= .020000001
    assert not any(r["record_id"] == "DEMO-100" for r in client.get("/api/records").json())


@pytest.mark.parametrize("change", [{"prepared_kg": -1}, {"consumed_kg": "NaN"}, {"date": "2026-99-01"}, {"date": "20261009"},
                                    {"prepared_kg": 101}, {"attendance": 1.2}, {"special_event": "holiday"}, {"cost_per_kg": "inf"}])
def test_invalid_csv_actionable_and_no_mutation(client, change):
    before = client.get("/api/overview").json()
    response = preview(client, [fixture(client, **change)])
    assert response.status_code == 200
    result = response.json()
    assert not result["valid"]
    assert result["errors"][0]["row"] == 2
    assert client.get("/api/overview").json() == before


def test_csv_duplicates_conflicts_and_limits(client):
    r = fixture(client)
    result = preview(client, [r, r]).json()
    assert not result["valid"]
    assert any(e["row"] == 3 and "Duplicate" in e["message"] for e in result["errors"])
    history = db.load_csv(DATA / "history_90_days.csv")
    assert not preview(client, [history[0]]).json()["valid"]
    large = client.post("/api/datasets/preview", files={"file": ("large.csv", b"x" * (5 * 1024 * 1024 + 1))})
    assert large.status_code == 422
    repeated = [{**r, "record_id": f"UPLOAD-{i}"} for i in range(10001)]
    assert preview(client, repeated).status_code == 422


def test_atomic_import_token_version_and_unverified_source(client):
    snapshot = prediction(client)
    history = db.load_csv(DATA / "history_90_days.csv")
    rows = [{**r, "record_id": "IMPORT-" + r["record_id"]} for r in history]
    before = client.get("/api/overview").json()
    p = preview(client, rows).json()
    assert p["valid"] and len(p["sha256"]) == 64
    assert client.get("/api/overview").json() == before
    assert client.post("/api/datasets/commit", json={"preview_token": "forged", "mode": "replace"}).status_code == 404
    response = client.post("/api/datasets/commit", json={"preview_token": p["preview_token"], "mode": "replace"})
    assert response.status_code == 200
    result = client.get("/api/overview").json()
    assert result["record_count"] == 270
    assert result["dataset_version"] > before["dataset_version"]
    assert result["sources"] == ["user_provided_unverified"]
    old_ids = snapshot["items"][0]["history_ids"]
    archived = client.get("/api/records", params={"ids": ",".join(old_ids)}).json()
    assert len(archived) == len(old_ids)
    assert all(r["source"] == "synthetic" for r in archived)
    assert client.get("/api/health").json()["dataset_source"] == "user_provided_unverified"
    assert client.post("/api/datasets/commit", json={"preview_token": p["preview_token"], "mode": "replace"}).status_code == 404


def test_preview_stales_and_transactional_actuals(client):
    p = preview(client, [fixture(client, record_id="IMPORT")]).json()
    log_fixture(client)
    assert client.post("/api/datasets/commit", json={"preview_token": p["preview_token"], "mode": "replace"}).status_code == 409
    assert client.post("/api/actuals", json={"records": [fixture(client, record_id="NEW"), fixture(client)]}).status_code == 409
    assert not any(r["record_id"] == "NEW" for r in client.get("/api/records").json())


def test_conflict_csv_row_numbers_survive_invalid_rows(client):
    history = db.load_csv(DATA / "history_90_days.csv")
    rows = [fixture(client, prepared_kg=-1), history[0], history[0]]
    errors = preview(client, rows).json()["errors"]
    assert any(e["row"] == 3 and "Existing" in e["message"] for e in errors)
    assert any(e["row"] == 4 and "Duplicate" in e["message"] for e in errors)


def test_concurrent_allocations_cannot_exceed_category(client):
    from concurrent.futures import ThreadPoolExecutor
    log_fixture(client)
    def allocate(_):
        return client.post("/api/recovery/batches", json={"record_id": "DEMO-100", "origin": "untouched_surplus", "quantity_kg": 6}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(allocate, range(2)))
    assert sorted(statuses) == [200, 422]
    assert sum(b["quantity_kg"] for b in client.get("/api/recovery/batches").json()) == 6


def test_forecast_reproducible_weighting_served_and_prior_dates(client):
    f1, f2 = prediction(client), prediction(client)
    a, b = f1["items"][0], f2["items"][0]
    assert a == b
    records = {r["record_id"]: r for r in client.get("/api/records").json()}
    rows = [records[id] for id in a["history_ids"]]
    assert all(r["date"] < "2026-10-09" for r in rows)
    ratios = [(r["consumed_kg"] + r["plate_waste_kg"]) / r["attendance"] for r in rows]
    assert a["demand_kg"] == pytest.approx(np.average(ratios, weights=np.arange(1, len(rows) + 1)) * 160)
    assert a["recommended_kg"] == pytest.approx(a["demand_kg"] * 1.05)
    consumed_only = np.average([r["consumed_kg"] / r["attendance"] for r in rows], weights=np.arange(1, len(rows) + 1)) * 160
    assert a["demand_kg"] > consumed_only
    assert a["range_low_kg"] == pytest.approx(np.percentile(np.array(ratios) * 160, 10))


def test_no_temporal_leakage_and_true_mae(client):
    f = prediction(client)["items"][0]
    records = {r["record_id"]: r for r in client.get("/api/records").json()}
    bt = f["backtest"]
    assert bt["evaluation_count"] == 14 and bt["attendance_known"]
    for e in bt["evaluations"]:
        assert all(records[id]["date"] < e["date"] for id in e["training_ids"])
    assert bt["mae_kg"] == pytest.approx(np.mean([abs(e["actual_served_kg"] - e["prediction_kg"]) for e in bt["evaluations"]]))
    assert bt["baseline_mae_kg"] == pytest.approx(np.mean([abs(e["actual_served_kg"] - e["baseline_kg"]) for e in bt["evaluations"]]))
    past = prediction(client, date="2026-09-01")["items"][0]
    log_fixture(client)
    assert prediction(client, date="2026-09-01")["items"][0] == past


def test_fallback_and_sparse_manual_quantity(client):
    f = prediction(client, special_event="festival")["items"][0]
    assert f["fallback_reason"] and f["sample_count"] == 14
    sparse = prediction(client, date="2026-07-13")["items"][0]
    assert sparse["status"] == "insufficient_data" and "demand_kg" not in sparse
    f = prediction(client, items=["New dish"])
    assert client.post("/api/simulate", json={"forecast_id": f["id"], "item": "New dish", "quantity_kg": 10, "baseline_prepared_kg": 20}).status_code == 422
    p = client.post("/api/plans", json={"forecast_id": f["id"], "quantities": {"New dish": 10}, "approved_by": "Manager"})
    assert p.status_code == 200 and p.json()["manual_items"] == ["New dish"]


def test_exact_simulator_fixture_and_negative_cost():
    f = json.loads((DATA / "simulator_fixture.json").read_text())
    result = domain.simulate(f["demand_samples_kg"], 85, 100, 45)
    assert result["expected_surplus_kg"] == pytest.approx(10 / 3)
    assert result["expected_shortage_kg"] == pytest.approx(1 / 3)
    assert result["shortage_frequency"] == pytest.approx(1 / 3)
    assert result["baseline"]["expected_surplus_kg"] == 18
    assert result["baseline"]["expected_shortage_kg"] == 0
    assert result["potential_cost_difference_inr"] == 675
    assert domain.simulate([78, 82, 86], 110, 100, 45)["potential_cost_difference_inr"] == -450
    lower = domain.simulate([78, 82, 86], 70, 100, 45)
    assert lower["expected_surplus_kg"] < result["expected_surplus_kg"] and lower["expected_shortage_kg"] > result["expected_shortage_kg"]


def test_persistent_approved_plan_actual_balance_feedback_and_report(client):
    f = prediction(client, date="2026-10-10")
    before_next = prediction(client, date="2026-10-17")["items"][0]
    p = client.post("/api/plans", json={"forecast_id": f["id"], "quantities": {"Rice": 50}, "approved_by": "Manager"}).json()
    with TestClient(app) as restarted:
        assert restarted.get("/api/plans").json()[0]["id"] == p["id"]
    bad = fixture(client, item="Rice", date="2026-10-10", prepared_kg=99)
    assert client.post("/api/actuals", json={"plan_id": p["id"], "records": [bad]}).status_code == 422
    r = fixture(client, item="Rice", date="2026-10-10")
    result = client.post("/api/actuals", json={"plan_id": p["id"], "records": [r]}).json()
    assert result["rows"][0]["served_kg"] == 90 and result["dataset_version"] > f["dataset_version"]
    assert client.post("/api/plans", json={"forecast_id": f["id"], "quantities": {"Rice": 50}, "approved_by": "Manager"}).status_code == 409
    next_forecast = prediction(client, date="2026-10-17")["items"][0]
    assert "DEMO-100" in next_forecast["history_ids"]
    assert next_forecast["demand_kg"] != before_next["demand_kg"]
    report = client.post("/api/report", json={"forecast_id": f["id"], "plan_id": p["id"]}).json()
    assert report["explanation_mode"] == "deterministic"
    assert report["evidence"]["dataset_version"] == f["dataset_version"]
    assert "food served" in report["explanation"]
    impact = client.get("/api/impact").json()
    assert impact["plans"][0]["actual_comparison"][0]["actual_served_kg"] == 90
    assert impact["simulated_dispositions"]["human_redistribution"] == 0


def test_plate_waste_never_enters_human_redistribution(client):
    log_fixture(client)
    b = batch(client, "plate_waste", 8)
    assert b["state"] == "blocked"
    assert review(client, b["id"]).json()["state"] == "blocked"
    assert approve(client, b["id"]).status_code == 422
    assert handoff(client, b["id"]).status_code == 422
    assert client.get("/api/impact").json()["simulated_dispositions"]["human_redistribution"] == 0


@pytest.mark.parametrize("value,expected", [(None, "pending_review"), (False, "blocked")])
def test_incomplete_failed_review_cannot_approve(client, value, expected):
    log_fixture(client)
    b = batch(client)
    assert approve(client, b["id"]).status_code == 422
    assert review(client, b["id"], storage_verified=value).json()["state"] == expected
    assert approve(client, b["id"]).status_code == 422


def test_review_eligibility_manager_approval_and_invalidation(client):
    log_fixture(client)
    b = batch(client)
    assert review(client, b["id"]).json()["state"] == "eligible_pending_approval"
    assert handoff(client, b["id"]).status_code == 422
    assert approve(client, b["id"]).json()["state"] == "approved_for_simulated_handoff"
    updated = review(client, b["id"], reviewer="Different staff").json()
    assert updated["approved_at"] is None and updated["state"] == "eligible_pending_approval"
    assert handoff(client, b["id"]).status_code == 422
    approve(client, b["id"])
    changed = client.patch(f"/api/recovery/batches/{b['id']}", json={"record_id": "DEMO-100", "origin": "plate_waste", "quantity_kg": 8}).json()
    assert changed["approved_at"] is None and changed["state"] == "blocked"
    assert handoff(client, b["id"]).status_code == 422


def test_duplicate_split_handoffs_and_allocation_limits(client):
    log_fixture(client)
    b = batch(client)
    review(client, b["id"])
    approve(client, b["id"])
    first = handoff(client, b["id"]).json()
    retry = handoff(client, b["id"]).json()
    assert retry["duplicate"] and first["id"] == retry["id"]
    assert handoff(client, b["id"], amount=4).status_code == 409
    assert handoff(client, b["id"], key="split-2", amount=6).status_code == 422
    assert handoff(client, b["id"], key="split-2", amount=5).status_code == 200
    assert client.get("/api/recovery/batches").json()[0]["handed_off_kg"] == 10
    assert client.post("/api/recovery/batches", json={"record_id": "DEMO-100", "origin": "untouched_surplus", "quantity_kg": 1}).status_code == 422
    assert client.get("/api/impact").json()["simulated_dispositions"]["human_redistribution"] == 10


def test_unknown_origin_unknown_processor_and_compost_separate(client):
    log_fixture(client)
    u = batch(client, "unknown", 1)
    assert u["state"] == "blocked"
    assert approve(client, u["id"]).status_code == 422
    assert handoff(client, u["id"], route="compost", partner="demo-compost").status_code == 422
    b = batch(client, "plate_waste", 8)
    assert handoff(client, b["id"], route="compost", partner="demo-unconfirmed").status_code == 422
    assert handoff(client, b["id"], route="compost", partner="demo-compost").status_code == 200
    result = client.get("/api/impact").json()["simulated_dispositions"]
    assert result["compost"] == 5 and result["human_redistribution"] == 0


def test_inventory_dates_unknown_storage_and_no_safe_claim(client):
    rows = {r["ingredient"]: r for r in client.get("/api/inventory?as_of=2026-10-09").json()["items"]}
    assert rows["Spinach"]["status"] == "expired"
    assert rows["Tomatoes"]["status"] == "near_expiry"
    assert rows["Paneer"]["storage_verified"] is None
    assert "review required" in rows["Paneer"]["storage_status"]
    due = client.get("/api/inventory?as_of=2026-10-10").json()
    assert next(r for r in due["items"] if r["ingredient"] == "Tomatoes")["status"] == "due_today"


def test_explicit_piece_conversion_and_nonfinite_actual():
    r = db.load_csv(DATA / "demo_accounting.csv")[0]
    with pytest.raises(ValidationError):
        Record.model_validate({**r, "display_qty": 100, "display_unit": "pieces"})
    with pytest.raises(ValidationError):
        Record.model_validate({**r, "display_qty": 100, "display_unit": "pieces", "piece_weight_kg": .04})
    assert Record.model_validate({**r, "display_qty": 2500, "display_unit": "pieces", "piece_weight_kg": .04}).prepared_kg == 100
    with pytest.raises(ValidationError):
        Record.model_validate({**r, "prepared_kg": float("nan")})


def test_findings_are_evidenced_computed_and_normalized(client):
    findings = client.get("/api/investigations").json()
    assert any(f["id"] == "friday-Rice" for f in findings)
    records = client.get("/api/records").json()
    rice = [r for r in records if r["item"] == "Rice"]
    plate = next(f for f in findings if f["id"] == "plate-Rice")
    assert plate["observed_metrics"]["plate_waste_per_diner_kg"] == pytest.approx(np.mean([r["plate_waste_kg"] / r["attendance"] for r in rice]))
    assert plate["sample_count"] == 90 and len(plate["evidence_record_ids"]) == 90


def test_empty_dataset_and_zero_waste(client):
    with db.connect(write=True) as conn:
        conn.execute("DELETE FROM records")
    assert client.get("/api/overview").json()["totals"]["prepared_kg"] == 0
    assert client.get("/api/investigations").json() == []
    assert prediction(client)["items"][0]["status"] == "insufficient_data"
    r = fixture(client, prepared_kg=82, untouched_surplus_kg=0, plate_waste_kg=0)
    assert client.post("/api/actuals", json={"records": [r]}).status_code == 200
    assert client.get("/api/overview").json()["totals"]["waste_kg"] == 0


def test_demo_reset_explicit_guard_and_offline_health(client, monkeypatch):
    log_fixture(client)
    assert client.post("/api/demo/reset", json={"confirm": "yes"}).status_code == 422
    monkeypatch.setenv("FOODWISE_DEMO", "false")
    assert client.post("/api/demo/reset", json={"confirm": "RESET SYNTHETIC DEMO"}).status_code == 409
    monkeypatch.setenv("FOODWISE_DEMO", "true")
    assert client.post("/api/demo/reset", json={"confirm": "RESET SYNTHETIC DEMO"}).status_code == 200
    assert client.get("/api/overview").json()["record_count"] == 270
    assert client.get("/api/health").json()["explanation_mode"] == "deterministic"
