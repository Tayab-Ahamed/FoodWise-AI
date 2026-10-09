from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import pytest
from backend.app import db
from backend.app.schemas import CHECKS


def setup_lunch(client, origin="untouched_surplus", quantity=10):
    record = client.get("/api/demo/accounting").json()
    assert client.post("/api/actuals", json={"records": [record]}).status_code == 200
    b = client.post("/api/recovery/batches", json={"record_id": record["record_id"], "origin": origin, "quantity_kg": quantity}).json()
    review(client, b["id"])
    client.post(f"/api/recovery/batches/{b['id']}/approve", json={"approved_by": "Kitchen manager"})
    return record, b


def review(client, id, **changes):
    return client.patch(f"/api/recovery/batches/{id}/review", json={**dict.fromkeys(CHECKS, True), "reviewer": "Staff", **changes})


def handling(**changes):
    start = datetime.fromisoformat("2026-10-09T13:00:00+05:30")
    return {"procedure_reference": "SYNTHETIC-HOT-HOLD-DEMO", "reviewer": "Staff",
            "holding_mode": "hot_held", "holding_started_at": start.isoformat(),
            "dinner_service_at": (start+timedelta(hours=6)).isoformat(),
            "temperatures": [{"at": (start+timedelta(hours=h)).isoformat(), "celsius": 65} for h in range(7)],
            "continuous_monitoring_verified": True, "procedure_allows_this_food": True,
            "protected_separate_container": True, **changes}


def proposal(client, batch, **changes):
    f = client.post("/api/forecast", json={"date": "2026-10-09", "meal": "dinner", "items": ["Mixed cooked meal"], "expected_attendance": 200}).json()
    return client.post("/api/reuse/proposals", json={"batch_id": batch["id"], "dinner_forecast_id": f["id"],
                       "quantity_kg": 10, "manual_dinner_total_kg": 20, "compatibility_confirmed": True, **changes})


def approve_reuse(client, p, **changes):
    return client.post(f"/api/reuse/proposals/{p['id']}/decision", json={"approved_by": "Kitchen manager", "decision": "approve",
                       "qualified_kitchen_manager": True, "procedure_review_confirmed": True, **changes})


def prepared(client):
    record, b = setup_lunch(client)
    assert client.patch(f"/api/reuse/batches/{b['id']}/evidence", json=handling()).status_code == 200
    p = proposal(client, b)
    assert p.status_code == 200, p.text
    return record, b, p.json()


def dinner(record, **changes):
    return {**record, "record_id": "DINNER-1", "meal": "dinner", "prepared_kg": 20,
            "consumed_kg": 18, "untouched_surplus_kg": 1, "plate_waste_kg": 1, **changes}


@pytest.mark.parametrize("changes", [
    {"holding_mode": "unknown"}, {"holding_mode": "chilled"}, {"holding_mode": "ambient"},
    {"continuous_monitoring_verified": None}, {"procedure_allows_this_food": False},
    {"protected_separate_container": None}, {"temperatures": []},
    {"holding_started_at": None}, {"dinner_service_at": "2026-10-10T19:00:00+05:30"},
    {"temperatures": [{"at": "2026-10-09T13:00:00+05:30", "celsius": 62}, {"at": "2026-10-09T19:00:00+05:30", "celsius": 65}]},
    {"holding_started_at": "2026-10-09T13:00:00"},
])
def test_unknown_unsafe_or_incomplete_evidence_cannot_reserve(client, changes):
    _, b = setup_lunch(client)
    client.patch(f"/api/reuse/batches/{b['id']}/evidence", json=handling(**changes))
    assert proposal(client, b).status_code == 422
    assert client.get("/api/reuse/plans").json() == []


def test_missing_evidence_and_qualified_manager_denied(client):
    _, b = setup_lunch(client)
    assert proposal(client, b).status_code == 422
    client.patch(f"/api/reuse/batches/{b['id']}/evidence", json=handling())
    p = proposal(client, b).json()
    assert approve_reuse(client, p, qualified_kitchen_manager=None).status_code == 422
    assert approve_reuse(client, p, procedure_review_confirmed=False).status_code == 422
    assert client.get("/api/reuse/plans").json()[0]["state"] == "pending"


def test_plate_permanently_blocked_from_reuse_and_human(client):
    _, b = setup_lunch(client, "plate_waste", 8)
    assert client.patch(f"/api/reuse/batches/{b['id']}/evidence", json=handling()).status_code == 422
    assert proposal(client, b, quantity_kg=8).status_code == 422
    r = client.post(f"/api/recovery/batches/{b['id']}/handoff", json={"route": "human_redistribution", "partner_id": "demo-community", "quantity_kg": 8, "idempotency_key": "plate-human"})
    assert r.status_code == 422


def test_shared_ledger_reject_release_concurrent_reservations(client):
    _, b = setup_lunch(client)
    client.patch(f"/api/reuse/batches/{b['id']}/evidence", json=handling())
    assert proposal(client, b, quantity_kg=10.1).status_code == 422
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda _: proposal(client, b, quantity_kg=6), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 422]
    p = next(r.json() for r in responses if r.status_code == 200)
    body = {"route": "biogas", "partner_id": "demo-biogas", "quantity_kg": 5, "idempotency_key": "reuse-conflict"}
    assert client.post(f"/api/recovery/batches/{b['id']}/handoff", json=body).status_code == 422
    assert client.post(f"/api/reuse/proposals/{p['id']}/decision", json={"approved_by": "Manager", "decision": "reject"}).status_code == 200
    assert proposal(client, b).status_code == 200


@pytest.mark.parametrize("change", ["handling", "base_review"])
def test_changed_evidence_invalidates_approval_and_blocks_actual(client, change):
    record, b, p = prepared(client)
    p = approve_reuse(client, p).json()
    if change == "handling":
        client.patch(f"/api/reuse/batches/{b['id']}/evidence", json=handling(procedure_allows_this_food=False))
    else:
        review(client, b["id"], contamination_check_passed=False)
    assert client.get("/api/reuse/plans").json()[0]["state"] == "invalidated"
    r = client.post("/api/actuals", json={"plan_id": p["plan_id"], "records": [dinner(record)]})
    assert r.status_code == 409
    assert client.get("/api/recovery/batches").json()[0]["remaining_kg"] == 10


def test_connected_outcome_immutable_source_feedback_and_persistence(client):
    record, b, p = prepared(client)
    assert p["fresh_preparation_kg"] == 10 and "Manual" in p["demand_basis"]
    p = approve_reuse(client, p).json()
    assert client.patch(f"/api/recovery/batches/{b['id']}", json={"record_id": record["record_id"], "origin": "untouched_surplus", "quantity_kg": 9}).status_code == 409
    assert client.post("/api/actuals", json={"plan_id": p["plan_id"], "records": [dinner(record, source="measured")]}).status_code == 422
    result = client.post("/api/actuals", json={"plan_id": p["plan_id"], "records": [dinner(record)]})
    assert result.status_code == 200, result.text
    assert result.json()["rows"][0]["served_kg"] == 19
    assert client.get("/api/circular/impact").json()["staff_recorded_reuse_kg"] == 10
    db.bootstrap()
    assert client.get("/api/reuse/plans").json()[0]["state"] == "completed"
    review(client, b["id"], storage_verified=False)
    assert client.get("/api/reuse/plans").json()[0]["state"] == "completed"
    assert client.get("/api/recovery/batches").json()[0]["remaining_kg"] == 0
    f = client.post("/api/forecast", json={"date": "2026-10-10", "meal": "dinner", "items": ["Mixed cooked meal"], "expected_attendance": 200}).json()
    assert f["items"][0]["sample_count"] == 1
    assert client.get("/api/impact").status_code == 200
    report = client.post("/api/report", json={"forecast_id": p["dinner_forecast_id"], "plan_id": p["plan_id"]}).json()
    assert report["evidence"]["reuse"]["state"] == "completed"
    assert "10.00 kg planned fresh preparation plus 10.00 kg reserved reuse" in report["explanation"]


def test_previously_allocated_and_unknown_origins_block(client):
    _, b = setup_lunch(client)
    client.patch(f"/api/reuse/batches/{b['id']}/evidence", json=handling())
    body = {"route": "compost", "partner_id": "demo-compost", "quantity_kg": 3, "idempotency_key": "compost-first"}
    assert client.post(f"/api/recovery/batches/{b['id']}/handoff", json=body).status_code == 200
    assert proposal(client, b).status_code == 422
    assert proposal(client, b, quantity_kg=7).status_code == 200


def test_dinner_sparse_manual_and_compatibility_required(client):
    _, b = setup_lunch(client)
    client.patch(f"/api/reuse/batches/{b['id']}/evidence", json=handling())
    assert proposal(client, b, manual_dinner_total_kg=None).status_code == 422
    assert proposal(client, b, compatibility_confirmed=None).status_code == 422
    assert proposal(client, b, manual_dinner_total_kg=9).status_code == 422


def test_biogas_independent_math_assumptions_snapshot_and_labels(client):
    _, b = setup_lunch(client, "plate_waste", 8)
    assumptions = client.get("/api/biogas/defaults").json()["assumptions"]
    body = {"batch_id": b["id"], "partner_id": "demo-biogas", "quantity_kg": 8, "segregation_confirmed": True, "assumptions": assumptions}
    potential = client.post("/api/biogas/estimate", json=body).json()
    assert potential["biogas_m3"] == pytest.approx(0.8)
    assert potential["electricity_kwh"] == pytest.approx(1.66992)
    assert potential["useful_heat_kwh"] == pytest.approx(2.14704)
    assert potential["useful_energy_kwh"] == pytest.approx(3.81696)
    assert potential["actual_measured_energy_kwh"] is None and "theoretical" in potential["label"]
    request = {"route": "biogas", "partner_id": "demo-biogas", "quantity_kg": 8, "segregation_confirmed": True,
               "biogas_assumptions": assumptions, "idempotency_key": "energy-1"}
    r = client.post(f"/api/recovery/batches/{b['id']}/handoff", json=request)
    assert r.status_code == 200 and r.json()["potential"]["assumptions"] == assumptions
    assert client.post(f"/api/recovery/batches/{b['id']}/handoff", json=request).json()["duplicate"]
    assert client.post(f"/api/recovery/batches/{b['id']}/handoff", json={**request, "biogas_assumptions": {**assumptions, "methane_fraction": .5}}).status_code == 409
    impact = client.get("/api/circular/impact").json()
    assert impact["actual_measured_energy_kwh"] is None and impact["simulated_biogas_kg"] == 8
    assert impact["potential_useful_energy_kwh"] == pytest.approx(3.81696)


@pytest.mark.parametrize("changes", [{"partner_id": "demo-unconfirmed"}, {"partner_id": "demo-community"}, {"segregation_confirmed": None},
                                     {"quantity_kg": 8.1}, {"assumptions": {"electricity_efficiency": .8, "heat_efficiency": .5}},
                                     {"assumptions": {"gas_m3_per_kg_wet": -1}}])
def test_biogas_invalid_processors_segregation_and_efficiency(client, changes):
    _, b = setup_lunch(client, "plate_waste", 8)
    r = client.post("/api/biogas/estimate", json={"batch_id": b["id"], "partner_id": "demo-biogas", "quantity_kg": 8, "segregation_confirmed": True, **changes})
    assert r.status_code == 422


def test_reset_clears_new_ledger_only_when_explicit(client):
    prepared(client)
    assert client.post("/api/demo/reset", json={"confirm": "RESET SYNTHETIC DEMO"}).status_code == 200
    assert client.get("/api/reuse/plans").json() == []


def test_unknown_allocations_share_total_pool_and_block_reuse(client):
    record, b = setup_lunch(client, quantity=9)
    client.patch(f"/api/reuse/batches/{b['id']}/evidence", json=handling())
    body = {"record_id": record["record_id"], "origin": "unknown", "quantity_kg": 1}
    unknown = client.post("/api/recovery/batches", json=body).json()
    assert proposal(client, b, quantity_kg=9).status_code == 422
    assert client.post("/api/recovery/batches", json={**body, "quantity_kg": 9}).status_code == 422
    assert client.patch(f"/api/recovery/batches/{unknown['id']}", json={**body, "quantity_kg": 10}).status_code == 422
    assert client.post("/api/recovery/batches", json={**body, "origin": "plate_waste", "quantity_kg": 8}).status_code == 200
    assert client.post("/api/recovery/batches", json={**body, "origin": "untouched_surplus", "quantity_kg": 1}).status_code == 422


def test_renewed_batch_approval_invalidates_unused_reuse(client):
    _, b, p = prepared(client)
    assert approve_reuse(client, p).status_code == 200
    assert client.post(f"/api/recovery/batches/{b['id']}/approve", json={"approved_by": "Another manager"}).status_code == 200
    assert client.get("/api/reuse/plans").json()[0]["state"] == "invalidated"
