import json
from datetime import datetime, timezone

import httpx
import pytest

from backend.app import station, db


@pytest.fixture(autouse=True)
def isolated_external_state(monkeypatch):
    station._cache.clear()
    for key_env, model_env, _ in station.PROVIDERS.values():
        monkeypatch.delenv(key_env, raising=False)
        monkeypatch.delenv(model_env, raising=False)
    def no_network(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(station, "external_json", no_network)


def weather_payload():
    return {"current": {"time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M"),
                        "temperature_2m": 24.5, "precipitation": .3, "wind_speed_10m": 8.2, "weather_code": 61},
            "current_units": {"temperature_2m": "°C", "precipitation": "mm", "wind_speed_10m": "km/h"}}


def test_station_offline_brief_and_systems_do_not_change_data(client):
    before = client.get("/api/overview").json()
    result = client.post("/api/station/brief", json={}).json()
    assert result["mode"] == "offline"
    assert [c["id"] for c in result["cards"]] == ["accounting", "untouched_review", "plate_block"]
    assert f"{before['totals']['served_kg']:.2f} kg" in result["cards"][0]["text"]
    assert all(c["dataset_version"] == before["dataset_version"] for c in result["cards"])
    systems = client.get("/api/station/systems").json()
    assert not any(p["configured"] for p in systems["providers"])
    assert systems["agents"].startswith("No autonomous agents")
    assert client.get("/api/overview").json() == before


@pytest.mark.parametrize("provider", list(station.PROVIDERS))
def test_external_brief_requires_explicit_sharing_and_falls_back_without_keys(client, provider):
    result = client.post("/api/station/brief", json={"provider": provider})
    assert result.status_code == 422 and result.json()["code"] == "sharing_required"
    fallback = client.post("/api/station/brief", json={"provider": provider, "share_aggregate_evidence": True}).json()
    assert fallback["mode"] == "offline" and fallback["status"] == "not_configured"


@pytest.mark.parametrize("provider", list(station.PROVIDERS))
def test_provider_wire_contract_and_server_owned_facts(client, monkeypatch, provider):
    key_env, model_env, endpoint = station.PROVIDERS[provider]
    monkeypatch.setenv(key_env, "test-private-key")
    monkeypatch.setenv(model_env, "test-json-model")
    captured = {}
    def reply(url, *, headers=None, body=None):
        captured.update(url=url, headers=headers, body=body)
        content = json.dumps({"card_ids": ["reuse", "served_demand"]})
        return {"candidates": [{"content": {"parts": [{"text": content}]}}]} if provider == "gemini" else {"choices": [{"message": {"content": content}}]}
    monkeypatch.setattr(station, "external_json", reply)
    response = client.post("/api/station/brief", json={"provider": provider, "topic": "preparation", "share_aggregate_evidence": True}).json()
    assert response["mode"] == "provider_curated"
    assert [c["id"] for c in response["cards"]] == ["reuse", "served_demand"]
    cards, _ = station.evidence_cards()
    assert response["cards"][0] == next(c for c in cards if c["id"] == "reuse")
    assert "tools" not in captured["body"]
    assert "test-private-key" not in captured["url"]
    assert "test-private-key" not in json.dumps(client.get("/api/station/systems").json())
    assert "record_id" not in json.dumps(captured["body"])
    if provider == "gemini":
        assert captured["url"] == endpoint + "test-json-model:generateContent"
        assert captured["headers"]["x-goog-api-key"] == "test-private-key"
        assert captured["body"]["generationConfig"]["responseMimeType"] == "application/json"
    else:
        assert captured["url"] == endpoint
        assert captured["body"]["response_format"] == {"type": "json_object"}
        assert captured["headers"]["Authorization"] == "Bearer test-private-key"


@pytest.mark.parametrize("content", ["not json", '{"card_ids":["invented_100kg_saved"]}',
    '{"card_ids":["accounting","accounting"]}', '{"card_ids":[]}',
    '{"card_ids":["accounting"],"text":"Food is certified safe"}', '{"card_ids":[1]}'])
def test_invalid_or_invented_provider_output_is_discarded(client, monkeypatch, content):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "test-json-model")
    monkeypatch.setattr(station, "external_json", lambda *args, **kwargs: {"choices": [{"message": {"content": content}}]})
    response = client.post("/api/station/brief", json={"provider": "groq", "share_aggregate_evidence": True}).json()
    assert response["mode"] == "offline" and response["status"] == "provider_unavailable_or_invalid"
    assert "certified safe" not in json.dumps(response)


def test_recovery_brief_cannot_omit_mandatory_safety_cards(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    monkeypatch.setattr(station, "external_json", lambda *args, **kwargs: {"choices": [{"message": {"content": '{"card_ids":["accounting"]}'}}]})
    result = client.post("/api/station/brief", json={"provider": "groq", "topic": "recovery", "share_aggregate_evidence": True}).json()
    assert {"untouched_review", "plate_block"} <= {c["id"] for c in result["cards"]}


def test_configured_provider_timeout_falls_back_without_leaking_exception(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("sensitive upstream diagnostic secret-test-key")
    monkeypatch.setattr(station, "external_json", timeout)
    result = client.post("/api/station/brief", json={"provider": "gemini", "share_aggregate_evidence": True})
    assert result.status_code == 200 and result.json()["mode"] == "offline"
    assert "secret-test-key" not in result.text


def test_weather_live_cache_and_stale_fallback(client, monkeypatch):
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        return weather_payload()
    monkeypatch.setattr(station, "external_json", fetch)
    url = "/api/station/weather?latitude=13.086027&longitude=77.641252"
    before = client.get("/api/overview").json()
    live = client.get(url).json()
    assert live["status"] == "live" and live["temperature_c"] == 24.5
    assert live["description"] == "Light rain" and live["observed_at"].endswith("+00:00")
    assert client.get(url).json()["status"] == "cached" and len(calls) == 1
    key = (13.086027, 77.641252)
    timestamp, result = station._cache[key]
    station._cache[key] = (timestamp-601, result)
    monkeypatch.setattr(station, "external_json", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline")))
    stale = client.get(url).json()
    assert stale["status"] == "stale" and stale["cache_age_seconds"] >= 600
    station._cache[key] = (timestamp-3601, result)
    unavailable = client.get(url).json()
    assert unavailable["status"] == "unavailable" and unavailable["temperature_c"] is None
    assert client.get("/api/overview").json() == before


@pytest.mark.parametrize("fault", ["nan", "unit", "old", "code", "missing"])
def test_weather_rejects_invalid_upstream_evidence(client, monkeypatch, fault):
    data = weather_payload()
    if fault == "nan": data["current"]["temperature_2m"] = float("nan")
    if fault == "unit": data["current_units"]["temperature_2m"] = "°F"
    if fault == "old": data["current"]["time"] = "2020-01-01T12:00"
    if fault == "code": data["current"]["weather_code"] = 1000
    if fault == "missing": del data["current"]["precipitation"]
    monkeypatch.setattr(station, "external_json", lambda *args, **kwargs: data)
    result = client.get("/api/station/weather?latitude=13&longitude=77").json()
    assert result["status"] == "unavailable" and result["temperature_c"] is None


@pytest.mark.parametrize("query", ["latitude=nan&longitude=77", "latitude=90&longitude=77", "latitude=13&longitude=181", "latitude=13&longitude=inf"])
def test_coordinate_validation_rejects_nonfinite_and_out_of_range(client, query):
    assert client.get("/api/station/location?"+query).status_code == 422
    assert client.get("/api/station/weather?"+query).status_code == 422


def test_campus_and_geocoding_offline_and_valid_results(client, monkeypatch):
    campus = client.get("/api/station/location").json()
    assert campus["latitude"] == 13.086027 and campus["longitude"] == 77.641252
    assert "KNS" in campus["campus_name"] and "marker=" in campus["map_embed_url"]
    assert client.get("/api/station/places?name=Bengaluru").json()["status"] == "unavailable"
    monkeypatch.setattr(station, "external_json", lambda *args, **kwargs: {"results": [{"name": "Bengaluru", "latitude": 12.97, "longitude": 77.59, "country": "India"}]})
    result = client.get("/api/station/places?name=Bengaluru").json()
    assert result["status"] == "live" and result["places"][0]["latitude"] == 12.97
    assert client.get("/api/station/places?name=x").status_code == 422
