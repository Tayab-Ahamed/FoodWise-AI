"""Optional external context and strictly constrained evidence curation.

Nothing in this module mutates kitchen records, forecasts or safety decisions.
Provider prose is never displayed: providers can select existing evidence IDs only.
"""
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Literal
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from . import db, domain
from .errors import DomainError

router = APIRouter(prefix="/api/station", tags=["Field station"])
PROVIDERS = {
    "groq": ("GROQ_API_KEY", "GROQ_MODEL", "https://api.groq.com/openai/v1/chat/completions"),
    "gemini": ("GEMINI_API_KEY", "GEMINI_MODEL", "https://generativelanguage.googleapis.com/v1beta/models/"),
    "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "https://openrouter.ai/api/v1/chat/completions"),
}
_cache = {}
_cache_lock = Lock()


def external_json(url, *, headers=None, body=None):
    # Fixed hosts only, no redirects; never log headers or provider response bodies.
    with httpx.Client(timeout=httpx.Timeout(9, connect=4), follow_redirects=False, trust_env=False) as client:
        response = client.get(url, headers=headers) if body is None else client.post(url, headers=headers, json=body)
        response.raise_for_status()
        if len(response.content) > 256_000:
            raise ValueError("Response too large")
        return response.json()


def location_metadata(latitude, longitude):
    # Bounding box construction belongs to the backend, including polar/dateline bounds.
    west, east = max(-180, longitude-.035), min(180, longitude+.035)
    south, north = max(-85, latitude-.025), min(85, latitude+.025)
    return {"latitude": latitude, "longitude": longitude,
            "map_embed_url": "https://www.openstreetmap.org/export/embed.html?" + urlencode({
                "bbox": f"{west},{south},{east},{north}", "layer": "mapnik", "marker": f"{latitude},{longitude}"}),
            "map_url": f"https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=14/{latitude}/{longitude}"}


@router.get("/location")
def location(latitude: float = Query(13.086027, ge=-85, le=85, allow_inf_nan=False),
             longitude: float = Query(77.641252, ge=-180, le=180, allow_inf_nan=False)):
    return {**location_metadata(latitude, longitude), "campus_name": "KNS Institute of Technology",
            "campus_address": "Hegde Nagar–Kogilu Road, Thirumenahalli, Yelahanka, Bengaluru",
            "campus_source": "https://knsit.com/wp-content/uploads/2024/05/7.1.1_Facilities_Provide_in_Campus.pdf",
            "location_note": "Approximate campus entrance point from KNSIT's published facilities document; not a surveyed kitchen location"}


@router.get("/places")
def places(name: str = Query(min_length=2, max_length=100)):
    try:
        payload = external_json("https://geocoding-api.open-meteo.com/v1/search?" + urlencode({
            "name": name.strip(), "count": 5, "language": "en", "format": "json"}))
        results = []
        for place in payload.get("results", [])[:5]:
            lat, lon = float(place["latitude"]), float(place["longitude"])
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-85 <= lat <= 85 and -180 <= lon <= 180):
                continue
            results.append({"name": str(place["name"])[:100], "region": str(place.get("admin1", ""))[:100],
                            "country": str(place.get("country", ""))[:100], **location_metadata(lat, lon)})
        return {"status": "live", "places": results, "source": "Open-Meteo / GeoNames"}
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
        return {"status": "unavailable", "places": [], "message": "City search is unavailable. Enter coordinates, or keep the example location."}


def weather_description(code):
    return {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
            51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
            61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
            71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Rain showers",
            81: "Rain showers", 82: "Heavy showers", 85: "Snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail"}.get(code, "Conditions unavailable")


@router.get("/weather")
def weather(latitude: float = Query(ge=-85, le=85, allow_inf_nan=False),
            longitude: float = Query(ge=-180, le=180, allow_inf_nan=False)):
    key, now = (latitude, longitude), time.time()
    with _cache_lock:
        cached = _cache.get(key)
    if cached and now-cached[0] < 600:
        return {**cached[1], "status": "cached", "cache_age_seconds": round(now-cached[0])}
    try:
        data = external_json("https://api.open-meteo.com/v1/forecast?" + urlencode({
            "latitude": latitude, "longitude": longitude, "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
            "timezone": "UTC", "forecast_days": 1}))
        current, units = data["current"], data["current_units"]
        for field, low, high, unit in [("temperature_2m", -100, 70, "°C"), ("precipitation", 0, 1000, "mm"), ("wind_speed_10m", 0, 500, "km/h")]:
            value = current[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high or units[field] != unit:
                raise ValueError("Invalid weather evidence")
        code = current["weather_code"]
        if isinstance(code, bool) or not isinstance(code, int) or code not in {0,1,2,3,45,48,51,53,55,56,57,61,63,65,66,67,71,73,75,77,80,81,82,85,86,95,96,99}:
            raise ValueError("Invalid weather code")
        observed = datetime.fromisoformat(current["time"]).replace(tzinfo=timezone.utc)
        if abs(now-observed.timestamp()) > 7200:
            raise ValueError("Provider observation is stale")
        result = {"status": "live", "observed_at": observed.isoformat(), "fetched_at": db.now(),
                  "temperature_c": current["temperature_2m"], "precipitation_mm": current["precipitation"],
                  "wind_kmh": current["wind_speed_10m"], "description": weather_description(code),
                  "source": "Open-Meteo", "source_url": "https://open-meteo.com/", "cache_age_seconds": 0,
                  "context": "Outdoor weather model estimate. Staff may review attendance assumptions; this does not alter forecasts or establish food holding temperatures."}
        with _cache_lock:
            if len(_cache) >= 128:
                _cache.pop(next(iter(_cache)))
            _cache[key] = (now, result)
        return result
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
        if cached and now-cached[0] < 3600:
            return {**cached[1], "status": "stale", "cache_age_seconds": round(now-cached[0])}
        return {"status": "unavailable", "source": "Open-Meteo", "temperature_c": None,
                "message": "Live weather is unavailable. Kitchen planning and safety review still work offline."}


@router.get("/systems")
def systems():
    return {"providers": [{"id": key, "configured": bool(os.getenv(config[0]) and os.getenv(config[1])),
                           "model": os.getenv(config[1], ""), "key_present": bool(os.getenv(config[0]))}
                          for key, config in PROVIDERS.items()],
            "forecast": {"name": "Attendance-scaled served-food model", "runtime": "Local Pandas + NumPy",
                         "target": "Consumed food + plate waste", "validation": "Rolling temporal backtests; past records only",
                         "challengers": ["Historical mean", "Recent per-diner mean", "Weekday baseline", "Ridge regression"]},
            "safety": "Deterministic FastAPI rules and manager approval; plate waste blocked from human redistribution",
            "ai_role": "The AI prep coach trains a calendar ridge model on earlier served-food records and validates it temporally. Groq prioritizes validated evidence when connected. Managers own decisions; the server supplies every displayed fact and number.",
            "agents": "No autonomous agents. Staff initiate each request and managers approve preparation and recovery.",
            "external_context": "OpenStreetMap map; Open-Meteo weather and city search, requested explicitly",
            "persistence": "SQLite on this computer; no data is uploaded automatically"}


def evidence_cards():
    with db.connect() as conn:
        rows = db.records(conn)
        totals = domain.overview(rows)["totals"]
        reuse = db.all_objects(conn, "reuse_plans")
        reused = sum(p["quantity_kg"] for p in reuse if p["state"] == "completed")
        version = db.version(conn)
        sources = sorted({r["source"] for r in rows})
    def card(id, title, text, path):
        return {"id": id, "title": title, "text": text, "path": path, "dataset_version": version,
                "sources": sources, "basis": "All active kitchen records"}
    return [
        card("accounting", "Follow the mass", f"Recorded preparation totals {totals['prepared_kg']:.2f} kg across meal services. Served food totals {totals['served_kg']:.2f} kg, including plate waste. Meal totals can include reused food more than once; the reuse ledger separates newly prepared food. These are accounting totals, not impact savings.", "overview"),
        card("served_demand", "Forecast what must be served", "The local model scales historical served food by expected attendance. Plate waste remains part of demand. Temporal backtests use strictly earlier records; sparse history requires manual preparation quantities.", "plan"),
        card("untouched_review", "Surplus needs a decision", f"Records contain {totals['untouched_surplus_kg']:.2f} kg of untouched surplus. Origin alone does not authorize reuse or redistribution. Document storage and handling evidence, then obtain manager approval under the applicable procedure.", "recovery"),
        card("plate_block", "Keep plate waste out of human recovery", f"Records contain {totals['plate_waste_kg']:.2f} kg of plate waste. The backend always blocks human redistribution of plate waste. Processor acceptance and segregation are required for simulated non-human pathways.", "recovery"),
        card("reuse", "A transfer, counted once", f"Staff have recorded {reused:.2f} kg of completed dinner reuse. This is a transfer between meal services, not new food or proven waste prevention. Synthetic records remain synthetic.", "impact"),
        card("biogas", "Potential is not production", "Biogas estimates use explicit editable assumptions. Handoffs are simulated; no measured gas, generated electricity, carbon savings or real partner acceptance is claimed.", "impact"),
    ], version


class BriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["offline", "groq", "gemini", "openrouter"] = "offline"
    topic: Literal["overview", "preparation", "recovery"] = "overview"
    share_aggregate_evidence: bool = False


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card_ids: list[str] = Field(min_length=1, max_length=3)


def provider_selection(provider, cards, topic):
    key_env, model_env, endpoint = PROVIDERS[provider]
    key, model = os.getenv(key_env), os.getenv(model_env)
    if not key or not model:
        return None, "not_configured"
    # Fixed JSON vocabulary, no user prompts, tools, browsing, reasoning loops or actions.
    prompt = ("Select up to three evidence cards most relevant to the topic. Return only a JSON object "
              'with one field: {"card_ids":["existing_id"]}. Use existing IDs exactly; do not add prose or fields. '
              + json.dumps({"topic": topic, "cards": [{"id": c["id"], "title": c["title"], "text": c["text"]} for c in cards]}))
    try:
        if provider == "gemini":
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model):
                raise ValueError("Invalid model identifier")
            response = external_json(endpoint + quote(model, safe="") + ":generateContent", headers={"x-goog-api-key": key},
                                     body={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                           "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 500}})
            content = "".join(part.get("text", "") for part in response["candidates"][0]["content"]["parts"])
        else:
            response = external_json(endpoint, headers={"Authorization": "Bearer " + key},
                                     body={"model": model, "messages": [{"role": "user", "content": prompt}],
                                           "response_format": {"type": "json_object"}, "max_tokens": 500})
            content = response["choices"][0]["message"]["content"]
        selected = Selection.model_validate_json(content).card_ids
        if len(set(selected)) != len(selected) or not set(selected) <= {c["id"] for c in cards}:
            raise ValueError("Unknown or duplicate evidence")
        return selected, "provider_curated"
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None, "provider_unavailable_or_invalid"


@router.post("/brief")
def brief(request: BriefRequest):
    if request.provider != "offline" and not request.share_aggregate_evidence:
        raise DomainError("sharing_required", "Confirm sharing aggregate evidence with the selected provider, or use the offline briefing.")
    cards, version = evidence_cards()
    defaults = {"overview": ["accounting", "untouched_review", "plate_block"],
                "preparation": ["served_demand", "accounting", "reuse"],
                "recovery": ["untouched_review", "plate_block", "biogas"]}
    selection, status = (None, "offline") if request.provider == "offline" else provider_selection(request.provider, cards, request.topic)
    ids = selection or defaults[request.topic]
    if request.topic == "recovery":
        ids = ["untouched_review", "plate_block"] + [id for id in ids if id not in {"untouched_review", "plate_block"}][:1]
    lookup = {c["id"]: c for c in cards}
    return {"mode": "provider_curated" if selection else "offline", "status": status,
            "requested_provider": request.provider, "dataset_version": version, "cards": [lookup[id] for id in ids],
            "generated_at": db.now(), "label": "Server-authored evidence; AI can select cards, never create facts or approve actions"}
