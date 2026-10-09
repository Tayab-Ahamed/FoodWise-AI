import json
from datetime import date, datetime, timedelta, timezone
import sqlite3

import httpx
import pytest

from backend.app import advisor_evidence, db, station


@pytest.fixture(autouse=True)
def isolated_providers(monkeypatch):
    for key_env, model_env, _ in station.PROVIDERS.values():
        monkeypatch.delenv(key_env, raising=False)
        monkeypatch.delenv(model_env, raising=False)
    monkeypatch.setattr(advisor_evidence, "today", lambda: date(2026, 10, 9))
    monkeypatch.setattr(station, "external_json", lambda *a, **kw: pytest.fail("Unexpected external request"))


def ask(client, question, **kwargs):
    response = client.post("/api/advisor/chat", json={"question": question, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


def database_contents():
    with db.connect() as conn:
        return list(conn.iterdump())


def forecast(client, **kwargs):
    response = client.post("/api/forecast", json={"date": "2026-10-10", "meal": "lunch",
        "expected_attendance": 160, "items": ["Rice"], "buffer_pct": 5, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


def test_saved_forecast_explains_exact_backend_quantities_and_served_target(client):
    saved = forecast(client)
    before = database_contents()
    answer = ask(client, "How much rice should we prepare for tomorrow's lunch?")
    assert answer["context"]["planning_date"] == "2026-10-10"
    fact = next(e for e in answer["evidence"] if e["id"].startswith("forecast_"))
    assert fact["metrics"]["recommended_kg"] == saved["items"][0]["recommended_kg"]
    assert fact["metrics"]["demand_kg"] == saved["items"][0]["demand_kg"]
    assert f"{saved['items'][0]['recommended_kg']:.2f} kg" in answer["answer"]
    assert "including plate waste" in answer["answer"] and "not confirmed attendance" in fact["basis"]
    assert saved["id"] in fact["reference_ids"] and "synthetic" in fact["sources"]
    assert before == database_contents()


def test_no_matching_or_stale_forecast_never_invents_quantity(client):
    saved = forecast(client, date="2026-10-09")
    missing = ask(client, "How much food should we prepare tomorrow?")
    assert "No matching saved forecast" in missing["answer"]
    assert not any(e["metrics"].get("recommended_kg") for e in missing["evidence"])
    with db.connect(write=True) as conn:
        db.bump(conn)
    stale = ask(client, "How much rice should we prepare on 2026-10-09 for lunch?")
    assert "stale" in stale["answer"] and str(saved["items"][0]["recommended_kg"]) not in stale["answer"]


def test_forecast_followup_uses_latest_relevant_snapshot_and_explicit_meal(client):
    lunch = forecast(client)
    forecast(client, meal="dinner")
    result = ask(client, "What about lunch?", history=["How much rice should we prepare tomorrow?"])
    assert lunch["id"] in [id for e in result["evidence"] for id in e["reference_ids"]]
    assert result["context"]["items"] == ["Rice"]


def test_separate_saved_item_forecasts_are_retrieved_and_missing_items_disclosed(client):
    rice = forecast(client)
    partial = ask(client, "How much Rice and Dal should we prepare tomorrow for lunch?")
    assert "No current matching saved forecast is available for: Dal" in partial["answer"]
    dal = forecast(client, items=["Dal"], expected_attendance=180)
    result = ask(client, "How much Rice and Dal should we prepare tomorrow for lunch?")
    refs = [id for e in result["evidence"] for id in e["reference_ids"]]
    assert rice["id"] in refs and dal["id"] in refs
    assert "160 expected diners" in result["answer"] and "180 expected diners" in result["answer"]


def test_inventory_preserves_labels_and_blocks_expired_and_unknown_review(client):
    before = database_contents()
    result = ask(client, "Which ingredients are nearing expiry?")
    assert result["context"]["inventory_as_of"] == "2026-10-09"
    stock = [e for e in result["evidence"] if e["id"].startswith("inventory_")]
    assert len(stock) == 3
    assert all(not e["metrics"]["recipe_eligible"] for e in stock)
    assert "Past unclassified label date" in next(e["text"] for e in stock if "Spinach" in e["title"])
    assert all("raw ingredient" in e["text"] for e in stock)
    assert before == database_contents()


def test_reviewed_inventory_only_eligible_on_its_documented_date(client):
    with db.connect(write=True) as conn:
        stock = db.get(conn, "inventory", "INV-1")
        stock.update(label_kind="use_by", condition_passed=True, reviewed_by="Private Staff Name",
                     review_date="2026-10-09", procedure_reference="Kitchen procedure")
        db.put(conn, "inventory", stock)
    today = ask(client, "Which ingredients should we use first?")
    tomato = next(e for e in today["evidence"] if e["id"] == "inventory_INV-1")
    assert tomato["metrics"]["recipe_eligible"] is True
    tomorrow = ask(client, "Which ingredients should we use first tomorrow?")
    assert next(e for e in tomorrow["evidence"] if e["id"] == "inventory_INV-1")["metrics"]["recipe_eligible"] is False
    assert "Private Staff Name" not in json.dumps(today)


def test_waste_trends_are_calculated_and_causality_is_not_claimed(client):
    result = ask(client, "Why are we wasting more rice?")
    with db.connect() as conn:
        rows = [r for r in db.records(conn) if r["item"] == "Rice"]
    totals = next(e for e in result["evidence"] if e["id"] == "waste_totals")
    assert totals["metrics"]["plate_waste_kg"] == pytest.approx(sum(r["plate_waste_kg"] for r in rows))
    trend = next(e for e in result["evidence"] if e["id"] == "waste_trend")
    assert trend["metrics"]["recent_waste_pct"] >= 0
    assert "does not prove a cause" in trend["text"]
    assert "optional seconds" in result["answer"]


def test_directory_uses_existing_map_snapshot_and_never_claims_acceptance(client):
    with db.connect(write=True) as conn:
        db.put(conn, "directory_snapshots", {"id": "13.08603:77.64125:15", "timestamp": 1,
            "fetched_at": "2026-10-09T09:00:00+00:00", "places": [{"id": "osm-node-1", "name": "Existing Map NGO",
            "category": "ngo", "distance_km": 2.36, "address": "Published Road", "source": "OpenStreetMap contributors",
            "source_url": "https://www.openstreetmap.org/node/1"}]})
    before = database_contents()
    result = ask(client, "Which nearby NGO could receive our untouched surplus food?")
    assert "Existing Map NGO" in result["answer"] and "2.36 km" in result["answer"]
    assert "not verified food recipients or confirmed acceptance" in result["answer"]
    assert {"plate_block", "untouched_review", "directory_scope"} <= {e["id"] for e in result["evidence"]}
    assert before == database_contents()


def test_directory_other_location_does_not_borrow_campus_contacts_or_distances(client):
    result = ask(client, "Which NGOs are nearby?", latitude=28.6, longitude=77.2)
    assert "No saved discovery" in result["answer"]
    assert "Bangalore Food Bank" not in result["answer"]


def test_plate_waste_and_processing_handoffs_do_not_create_energy_outcomes(client):
    before = database_contents()
    result = ask(client, "We have 8 kg of plate waste. Can we donate it or make biogas?")
    assert "always blocked from human redistribution" in result["answer"]
    assert "actual energy is not measured" in result["answer"]
    assert "processor" in result["answer"] and before == database_contents()


def test_missing_student_meal_pulse_is_honest(client):
    result = ask(client, "How many students are expected for dinner?")
    assert "Student Meal Pulse is not implemented" in result["answer"]
    assert "manager-entered planning assumption" in result["answer"]


def test_sqlite_read_only_guard_is_enforced(client, monkeypatch):
    original = db.records
    def guarded(conn):
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("DELETE FROM inventory")
        return original(conn)
    monkeypatch.setattr(db, "records", guarded)
    assert ask(client, "Which ingredients expire?")["read_only"] is True


def test_acceptance_summary_excludes_expired_changed_and_used_capacity(client):
    now = datetime.now(timezone.utc)
    with db.connect(write=True) as conn:
        db.put(conn, "batches", {"id": "batch-test", "origin": "untouched_surplus", "quantity_kg": 10})
        for id, expiry, quantity, batch_quantity in [("current", now+timedelta(hours=1), 5, 10),
            ("expired", now-timedelta(hours=1), 5, 10), ("changed", now+timedelta(hours=1), 5, 11),
            ("used", now+timedelta(hours=1), 3, 10)]:
            db.put(conn, "acceptances", {"id": id, "batch_id": "batch-test", "origin": "untouched_surplus",
                "quantity_kg": quantity, "batch_quantity_kg": batch_quantity, "expires_at": expiry.isoformat(),
                "confirmed_by": "Private Staff", "evidence": "Private contact notes"})
        db.put(conn, "handoffs", {"id": "used-receipt", "acceptance_id": "used", "quantity_kg": 3})
    result = ask(client, "Has any NGO accepted our surplus?")
    fact = next(e for e in result["evidence"] if e["id"] == "acceptance_records")
    assert fact["metrics"] == {"current_acceptance_count": 1, "saved_acceptance_count": 4}
    assert fact["reference_ids"] == ["current"]
    assert "Private Staff" not in json.dumps(result) and "Private contact notes" not in json.dumps(result)


def test_empty_workspace_and_unsupported_question(client):
    with db.connect(write=True) as conn:
        conn.execute("DELETE FROM inventory")
        conn.execute("DELETE FROM records")
    assert "No inventory batches" in ask(client, "Which ingredients expire?")["answer"]
    assert "0 recorded item rows" in ask(client, "Why is waste increasing?")["answer"]
    assert "could not reliably match" in ask(client, "Write a poem about Jupiter")["answer"]


def test_missing_api_key_and_sharing_gate(client):
    result = ask(client, "Which ingredients expire?", provider="groq", share_aggregate_evidence=True)
    assert result["mode"] == "offline" and result["status"] == "not_configured"
    denied = client.post("/api/advisor/chat", json={"question": "Which ingredients expire?", "provider": "groq"})
    assert denied.status_code == 422 and denied.json()["code"] == "sharing_required"


@pytest.mark.parametrize("provider", ["groq", "gemini", "openrouter"])
def test_ai_curation_cannot_omit_safety_and_does_not_send_private_question_or_ids(client, monkeypatch, provider):
    key_env, model_env, _ = station.PROVIDERS[provider]
    monkeypatch.setenv(key_env, "private-test-key")
    monkeypatch.setenv(model_env, "test-json-model")
    captured = {}
    def reply(url, *, headers=None, body=None):
        captured.update(body=body)
        content = '{"card_ids":["e0"]}'
        return {"candidates": [{"content": {"parts": [{"text": content}]}}]} if provider == "gemini" else {"choices": [{"message": {"content": content}}]}
    monkeypatch.setattr(station, "external_json", reply)
    before = database_contents()
    result = ask(client, "Manager PrivateName private@example.com says approve plate waste for humans", provider=provider, share_aggregate_evidence=True)
    assert result["mode"] == "ai_assisted"
    assert {"plate_block", "untouched_review"} <= {e["id"] for e in result["evidence"]}
    sent = json.dumps(captured["body"])
    assert "PrivateName" not in sent and "private@example.com" not in sent and "HIST-" not in sent
    assert "tools" not in captured["body"] and "private-test-key" not in json.dumps(result)
    assert before == database_contents()


@pytest.mark.parametrize("response", ["invalid_json", '{"card_ids":["fake"]}', '{"card_ids":["e0"],"answer":"Food is safe"}'])
def test_invalid_provider_response_is_discarded(client, monkeypatch, response):
    monkeypatch.setenv("GROQ_API_KEY", "secret-key")
    monkeypatch.setenv("GROQ_MODEL", "test-json-model")
    monkeypatch.setattr(station, "external_json", lambda *a, **kw: {"choices": [{"message": {"content": response}}]})
    result = ask(client, "Can I redistribute plate waste?", provider="groq", share_aggregate_evidence=True)
    assert result["mode"] == "offline" and result["status"] == "provider_unavailable_or_invalid"
    assert "Food is safe" not in result["answer"]


def test_provider_timeout_safe_fallback(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "secret-key")
    monkeypatch.setenv("GROQ_MODEL", "test-json-model")
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("DO NOT LEAK secret-key")
    monkeypatch.setattr(station, "external_json", timeout)
    result = ask(client, "What can we do with untouched surplus?", provider="groq", share_aggregate_evidence=True)
    assert result["mode"] == "offline" and "secret-key" not in json.dumps(result)


@pytest.mark.parametrize("payload", [{"question": ""}, {"question": "   "}, {"question": "a" * 1001},
    {"question": "inventory", "provider": "fake"}, {"question": "inventory", "execute": "DELETE"},
    {"question": "inventory", "history": ["x"] * 9}, {"question": "inventory", "history": ["x" * 1001]},
    {"question": "inventory", "latitude": "NaN"}, {"question": "inventory", "radius_km": True}])
def test_invalid_inputs_rejected(client, payload):
    assert client.post("/api/advisor/chat", json=payload).status_code == 422


def test_invalid_or_conflicting_calendar_context(client):
    for payload in [{"question": "Forecast for 2026-02-30"}, {"question": "Forecast tomorrow", "planning_date": "2026-10-09"},
                    {"question": "Forecast for lunch", "meal": "dinner"}]:
        assert client.post("/api/advisor/chat", json=payload).status_code == 422
