import json
from datetime import datetime, timedelta, timezone

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app import db, domain, intelligence, recipients, station
from backend.app.main import app
from backend.app.schemas import CHECKS


@pytest.fixture(autouse=True)
def isolate_network(monkeypatch):
    recipients._cache.clear()
    def offline(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(recipients, "fetch_places", offline)
    monkeypatch.setattr(station, "external_json", offline)
    for key, model, _ in station.PROVIDERS.values():
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(model, raising=False)


def forecast(client, **kwargs):
    response = client.post("/api/forecast", json={"date": "2026-10-09", "meal": "lunch", "expected_attendance": 160, "items": ["Rice"], **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


def setup_recipient(client, source="measured", origin="untouched_surplus", reviewed=True, category="ngo"):
    record = {**client.get("/api/demo/accounting").json(), "record_id": "RECEIPT-TEST", "source": source}
    assert client.post("/api/actuals", json={"records": [record]}).status_code == 200
    batch = client.post("/api/recovery/batches", json={"record_id": record["record_id"], "origin": origin, "quantity_kg": 5}).json()
    if reviewed:
        client.patch(f"/api/recovery/batches/{batch['id']}/review", json={**{k: True for k in CHECKS}, "reviewer": "Reviewer"})
        client.post(f"/api/recovery/batches/{batch['id']}/approve", json={"approved_by": "Manager"})
    recipient = client.post("/api/recipients", json={"name": "Test recipient", "address": "Test collection address", "contact": "staff@example.test", "category": category}).json()
    acceptance = {"recipient_id": recipient["id"], "batch_id": batch["id"], "route": "human_redistribution", "quantity_kg": 4,
                  "confirmed_by": "Kitchen staff", "contact_person": "Recipient staff", "evidence": "Telephone agreement for this batch; collect with labelled containers",
                  "expires_at": (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    return batch, recipient, acceptance


def receipt(acceptance_id, **kwargs):
    return {"acceptance_id": acceptance_id, "quantity_kg": 3, "received_by": "Recipient staff", "receipt_reference": "TEST-RECEIPT-1",
            "handoff_occurred": True, "segregation_confirmed": True, "idempotency_key": "network-receipt-1", **kwargs}


def test_directory_offline_contacts_are_not_invented_pins_or_partners(client):
    result = client.get("/api/recipients/directory").json()
    assert result["status"] == "not_requested" and result["places"] == []
    assert result["contacts"][0]["source_url"] == "https://bangalorefoodbank.com/get-involved.html"
    assert all(c["latitude"] is None and c["acceptance_status"] == "contact_required" for c in result["contacts"])
    assert client.get("/api/recipients/directory?discover=true").json()["status"] == "unavailable"
    assert client.get("/api/recipients/directory?latitude=0&longitude=0").json()["contacts"] == []


def test_directory_validates_deduplicates_distances_and_caches(client, monkeypatch):
    payload = {"elements": [
        {"type": "node", "id": 1, "lat": 13.09, "lon": 77.64, "tags": {"name": "Mapped NGO", "office": "ngo", "website": "javascript:alert(1)"}},
        {"type": "way", "id": 2, "center": {"lat": 13.1, "lon": 77.64}, "tags": {"name": "Food bank", "social_facility": "food_bank"}},
        {"type": "node", "id": 3, "lat": 13.09, "lon": 77.64, "tags": {"name": "Mapped NGO"}},
        {"type": "node", "id": 4, "lat": 80, "lon": 77, "tags": {"name": "Far away"}},
        {"type": "node", "id": 5, "lat": float("nan"), "lon": 77, "tags": {"name": "Bad coordinate"}},
    ]}
    captured = []
    def fetch(query): captured.append(query); return payload
    monkeypatch.setattr(recipients, "fetch_places", fetch)
    result = client.get("/api/recipients/directory?discover=true&radius_km=5").json()
    assert result["status"] == "live" and len(result["places"]) == 2
    assert result["places"][0]["website"] == "" and result["places"][0]["distance_km"] < 1
    assert "around:5000,13.086027,77.641252" in captured[0]
    assert client.get("/api/recipients/directory?discover=true&radius_km=5").json()["status"] == "cached"
    assert len(captured) == 1
    recipients._cache.clear()
    assert client.get("/api/recipients/directory?radius_km=5").json()["places"] == result["places"]
    # Repopulate the in-memory view, then exercise stale upstream failure.
    with recipients._lock:
        recipients._cache[(13.08603, 77.64125, 5)] = (recipients.time.time(), result["places"], result["fetched_at"])
    with recipients._lock:
        key = next(iter(recipients._cache)); stamp, places, fetched = recipients._cache[key]
        recipients._cache[key] = (stamp-4000, places, fetched)
    monkeypatch.setattr(recipients, "fetch_places", lambda q: {"remark": "timeout", "elements": []})
    stale = client.get("/api/recipients/directory?discover=true&radius_km=5").json()
    assert stale["status"] == "stale" and len(stale["places"]) == 2


@pytest.mark.parametrize("query", ["latitude=nan", "longitude=181", "radius_km=31", "radius_km=0"])
def test_directory_rejects_invalid_bounds(client, query):
    assert client.get("/api/recipients/directory?"+query).status_code == 422


def test_saved_contact_is_not_acceptance_and_validates_source(client):
    good = {"name": "Known recipient", "address": "Collection address", "contact": "staff@example.test"}
    assert client.post("/api/recipients", json={**good, "latitude": 13}).status_code == 422
    assert client.post("/api/recipients", json={**good, "source_url": "javascript:foo"}).status_code == 422
    assert client.post("/api/recipients", json=good).json()["acceptance_status"] == "contact_required"
    assert len(client.get("/api/recipients/directory").json()["saved"]) == 1
    assert client.get("/api/recipients/acceptances").json() == []


def test_measured_dispatch_atomic_capacity_idempotency_and_impact(client):
    batch, _, acceptance = setup_recipient(client)
    accepted = client.post("/api/recipients/acceptances", json=acceptance)
    assert accepted.status_code == 200, accepted.text
    intent = receipt(accepted.json()["id"])
    first = client.post("/api/recipients/dispatch", json=intent)
    assert first.status_code == 200, first.text
    assert not first.json()["simulated"] and first.json()["recipient_snapshot"]["name"] == "Test recipient"
    retry = client.post("/api/recipients/dispatch", json=intent).json()
    assert retry["duplicate"] and retry["id"] == first.json()["id"]
    assert client.post("/api/recipients/dispatch", json={**intent, "quantity_kg": 2}).status_code == 409
    assert client.post("/api/recipients/dispatch", json={**intent, "idempotency_key": "receipt-two", "quantity_kg": 2}).json()["code"] == "handoff_exceeded"
    assert client.get("/api/recipients/acceptances").json()[0]["remaining_kg"] == 1
    assert len(client.get("/api/recipients/dispatch").json()) == 1
    impact = client.get("/api/impact").json()
    assert impact["recorded_dispositions"]["human_redistribution"] == 3
    assert impact["simulated_dispositions"]["human_redistribution"] == 0
    assert client.get("/api/recovery/batches").json()[0]["remaining_kg"] == 2


@pytest.mark.parametrize("source", ["synthetic", "user_provided_unverified"])
def test_generated_and_unverified_records_cannot_make_real_receipts(client, source):
    _, _, acceptance = setup_recipient(client, source=source)
    accepted = client.post("/api/recipients/acceptances", json=acceptance).json()
    blocked = client.post("/api/recipients/dispatch", json=receipt(accepted["id"]))
    assert blocked.status_code == 422 and blocked.json()["code"] == "measured_record_required"
    assert client.get("/api/recipients/dispatch").json() == []


def test_plate_review_cannot_authorize_human_acceptance(client):
    _, _, acceptance = setup_recipient(client, origin="plate_waste")
    assert client.post("/api/recipients/acceptances", json=acceptance).json()["code"] == "recovery_blocked"


def test_measured_handoff_requires_current_manager_review_and_acceptance(client):
    batch, _, acceptance = setup_recipient(client, reviewed=False)
    a = client.post("/api/recipients/acceptances", json=acceptance).json()
    assert client.post("/api/recipients/dispatch", json=receipt(a["id"])).json()["code"] == "recovery_blocked"
    assert client.post("/api/recipients/acceptances", json={**acceptance, "expires_at": datetime.now(timezone.utc).isoformat()}).status_code == 422
    assert client.post("/api/recipients/acceptances", json={**acceptance, "expires_at": (datetime.now()+timedelta(hours=1)).isoformat()}).status_code == 422
    client.patch(f"/api/recovery/batches/{batch['id']}", json={"record_id": "RECEIPT-TEST", "origin": "untouched_surplus", "quantity_kg": 4})
    assert client.post("/api/recipients/dispatch", json=receipt(a["id"])).json()["code"] == "stale_acceptance"


def test_organic_route_needs_processor_acceptance_and_segregation(client):
    _, _, a = setup_recipient(client, origin="plate_waste", category="organic_processor")
    a["route"] = "biogas"
    accepted = client.post("/api/recipients/acceptances", json=a).json()
    assert client.post("/api/recipients/dispatch", json=receipt(accepted["id"], segregation_confirmed=False)).status_code == 422
    assert client.post("/api/recipients/dispatch", json=receipt(accepted["id"])).status_code == 200
    assert client.get("/api/circular/impact").json()["simulated_biogas_kg"] == 0


def test_ai_trains_temporally_includes_plate_and_retains_evidence_in_plan(client):
    f = forecast(client)
    result = client.post("/api/intelligence/prepare", json={"forecast_id": f["id"]}).json()
    item = result["items"][0]
    assert item["status"] == "ready" and item["evaluation_count"] == 14
    rows = {r["record_id"]: r for r in client.get("/api/records").json()}
    assert max(rows[id]["date"] for id in item["training_ids"]) < "2026-10-09"
    for evaluation in item["evaluations"]:
        assert all(rows[id]["date"] < evaluation["date"] for id in evaluation["training_ids"])
        row = rows[evaluation["record_id"]]
        assert evaluation["actual_served_kg"] == pytest.approx(row["consumed_kg"]+row["plate_waste_kg"])
    actual = np.array([r["actual_served_kg"] for r in item["evaluations"]])
    predicted = np.array([r["prediction_kg"] for r in item["evaluations"]])
    assert item["metrics"]["mae_kg"] == pytest.approx(np.abs(predicted-actual).mean())
    plan = client.post("/api/plans", json={"forecast_id": f["id"], "quantities": {"Rice": item["recommended_kg"]}, "approved_by": "Manager", "coach_id": result["id"]})
    assert plan.status_code == 200 and plan.json()["ai_evidence"]["id"] == result["id"]
    later = forecast(client, date="2026-10-10")
    assert client.post("/api/plans", json={"forecast_id": later["id"], "quantities": {"Rice": 40}, "approved_by": "Manager", "coach_id": result["id"]}).status_code == 409


def test_ai_shortage_preference_monotone_and_sparse_no_fabrication(client):
    f = forecast(client)
    low = client.post("/api/intelligence/prepare", json={"forecast_id": f["id"], "shortage_weight": 1}).json()["items"][0]
    high = client.post("/api/intelligence/prepare", json={"forecast_id": f["id"], "shortage_weight": 9}).json()["items"][0]
    assert low["recommended_kg"] <= high["recommended_kg"]
    assert low["scenario_outcomes"]["expected_surplus_kg"] <= high["scenario_outcomes"]["expected_surplus_kg"]
    sparse = forecast(client, date="2026-07-12")
    item = client.post("/api/intelligence/prepare", json={"forecast_id": sparse["id"]}).json()["items"][0]
    assert item["status"] == "collect_history" and "recommended_kg" not in item


def test_ai_confirmed_shortage_requires_manual_judgment(client):
    row = {**client.get("/api/demo/accounting").json(), "record_id": "AI-SHORTAGE", "item": "Rice", "date": "2026-10-09", "service_shortage_reported": True}
    assert client.post("/api/actuals", json={"records": [row]}).status_code == 200
    f = forecast(client, date="2026-10-10")
    item = client.post("/api/intelligence/prepare", json={"forecast_id": f["id"]}).json()["items"][0]
    assert item["shortage_reported_count"] == 1 and not item["recommendation_allowed"]


def test_concurrent_dispatches_cannot_overdraw_batch(client):
    from concurrent.futures import ThreadPoolExecutor
    _, _, acceptance = setup_recipient(client)
    acceptance["quantity_kg"] = 5
    a = client.post("/api/recipients/acceptances", json=acceptance).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(client.post, "/api/recipients/dispatch", json=receipt(a["id"], quantity_kg=3, idempotency_key=f"concurrent-{i}")) for i in range(2)]
        statuses = sorted(call.result().status_code for call in calls)
    assert statuses == [200, 422]
    assert sum(h["quantity_kg"] for h in client.get("/api/recipients/dispatch").json()) == 3


def test_groq_cannot_create_facts_and_requires_sharing(client, monkeypatch):
    f = forecast(client)
    assert client.post("/api/intelligence/prepare", json={"forecast_id": f["id"], "use_groq": True}).status_code == 422
    fallback = client.post("/api/intelligence/prepare", json={"forecast_id": f["id"], "use_groq": True, "share_aggregate_evidence": True}).json()
    assert fallback["groq_status"] == "not_configured" and fallback["items"][0]["status"] == "ready"
    monkeypatch.setenv("GROQ_API_KEY", "private-test-key"); monkeypatch.setenv("GROQ_MODEL", "test-model")
    captured = {}
    def reply(url, **kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": json.dumps({"card_ids": ["dish_0"], "approved": True})}}]}
    monkeypatch.setattr(station, "external_json", reply)
    invalid = client.post("/api/intelligence/prepare", json={"forecast_id": f["id"], "use_groq": True, "share_aggregate_evidence": True}).json()
    assert invalid["groq_status"] == "provider_unavailable_or_invalid"
    assert "record_id" not in json.dumps(captured["body"]) and "training_ids" not in json.dumps(captured["body"])
    assert "private-test-key" not in json.dumps(invalid)


def test_operations_workspace_starts_clean_and_preserves_practice_database(tmp_path, monkeypatch):
    monkeypatch.setenv("FOODWISE_DEMO", "false"); monkeypatch.setenv("FOODWISE_DB", str(tmp_path/"operations.sqlite3"))
    with TestClient(app) as client:
        assert client.get("/api/overview").json()["record_count"] == 0
        assert not client.get("/api/health").json()["practice_workspace"]
        assert client.get("/api/health").json()["dataset_source"] == "empty"
        assert client.get("/api/demo/accounting").status_code == 409
        assert client.post("/api/demo/reset", json={"confirm": "RESET SYNTHETIC DEMO"}).status_code == 409
        assert client.post("/api/recovery/batches/nonexistent/handoff", json={"route": "compost", "partner_id": "demo-compost", "quantity_kg": 1, "idempotency_key": "test"}).status_code == 409
        f = forecast(client)
        assert client.post("/api/intelligence/prepare", json={"forecast_id": f["id"]}).json()["items"][0]["status"] == "collect_history"
        row = {**db.load_csv(db.ROOT/"data"/"demo_accounting.csv")[0], "record_id": "OPS-TEST-MEASURED", "source": "measured"}
        assert client.post("/api/actuals", json={"records": [row]}).status_code == 200
        assert client.get("/api/health").json()["dataset_source"] == "measured"
