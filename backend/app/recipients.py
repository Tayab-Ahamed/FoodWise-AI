"""Sourced directory, staff contact attestations and atomic, measured dispatch ledger.

Discovery is never proof of acceptance. No organization is messaged by this module.
"""
import math
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Query
from pydantic import Field, field_validator, model_validator

from . import db, domain
from .schemas import StrictModel
from .errors import DomainError

router = APIRouter(prefix="/api/recipients", tags=["Recipient network"])
_cache = {}
_lock = Lock()
CONTACTS = [
    {"id": "bangalore-food-bank", "name": "Bangalore Food Bank", "category": "food_bank",
     "address": "Site No. 3 & 4, KHB Colony, Airport By-Pass Road, Yelahanka, Bengaluru 560064",
     "phone": "+91 8867853278", "email": "info@bangalorefoodbank.com",
     "website": "https://bangalorefoodbank.com/get-involved.html",
     "source_url": "https://bangalorefoodbank.com/get-involved.html", "source": "Organization website · checked 9 Oct 2026",
     "latitude": None, "longitude": None, "distance_km": None, "acceptance_status": "contact_required",
     "note": "Official food-donation contact in Yelahanka. Exact coordinates and acceptance of this cooked-food batch require confirmation."},
    {"id": "robin-hood-army", "name": "Robin Hood Army", "category": "food_rescue_network",
     "address": "Bengaluru volunteer coordination · confirm local collection point",
     "phone": "", "email": "", "website": "https://robinhoodarmy.com/",
     "source_url": "https://robinhoodarmy.com/", "source": "Organization website · checked 9 Oct 2026",
     "latitude": None, "longitude": None, "distance_km": None, "acceptance_status": "contact_required",
     "note": "Volunteer food-rescue network. Collection depends on local availability; no pickup or partnership is implied."},
]


def distance_km(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat2-lat1), math.radians(lon2-lon1)
    value = math.sin(a/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(b/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, value))))


def safe_url(value):
    if not isinstance(value, str) or len(value) > 500:
        return ""
    parsed = urlparse(value)
    return value if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password else ""


def fetch_places(query):
    with httpx.Client(timeout=httpx.Timeout(25, connect=5), follow_redirects=False, trust_env=False) as client:
        response = client.post("https://overpass-api.de/api/interpreter", data={"data": query},
                               headers={"User-Agent": "FoodWise/1.2 (local recipient directory)"})
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("Directory response too large")
        return response.json()


def parse_places(payload, latitude, longitude, radius_km):
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list) or payload.get("remark"):
        raise ValueError("Incomplete directory response")
    result, seen = [], set()
    for element in payload["elements"][:3000]:
        try:
            tags = element.get("tags", {})
            kind, osm_id = element["type"], int(element["id"])
            if kind not in {"node", "way", "relation"} or osm_id <= 0:
                continue
            name = str(tags.get("name") or tags.get("operator") or "").strip()[:150]
            if not name:
                continue
            point = element if kind == "node" else element["center"]
            lat, lon = float(point["lat"]), float(point["lon"])
            if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat) > 85 or abs(lon) > 180:
                continue
            distance = distance_km(latitude, longitude, lat, lon)
            if distance > radius_km or (name.casefold(), round(lat, 4), round(lon, 4)) in seen:
                continue
            category = tags.get("social_facility", "ngo" if tags.get("office") == "ngo" else "social_facility")
            if tags.get("amenity") == "waste_disposal" or tags.get("recycling:organic") == "yes":
                category = "organic_processor"
            if category not in {"food_bank", "soup_kitchen", "ngo", "social_facility", "organic_processor", "shelter", "group_home"}:
                category = "social_facility"
            seen.add((name.casefold(), round(lat, 4), round(lon, 4)))
            result.append({"id": f"osm-{kind}-{osm_id}", "name": name, "category": category,
                           "latitude": lat, "longitude": lon, "distance_km": round(distance, 2),
                           "address": ", ".join(str(tags[k])[:120] for k in ["addr:housenumber", "addr:street", "addr:suburb", "addr:city"] if tags.get(k)),
                           "phone": str(tags.get("contact:phone", tags.get("phone", "")))[:100],
                           "email": str(tags.get("contact:email", tags.get("email", "")))[:150],
                           "website": safe_url(tags.get("contact:website", tags.get("website", ""))),
                           "source": "OpenStreetMap contributors", "source_url": f"https://www.openstreetmap.org/{kind}/{osm_id}",
                           "acceptance_status": "contact_required", "note": "Community-mapped candidate. Verify activity, contact, material acceptance and collection arrangements."})
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    return sorted(result, key=lambda r: (r["distance_km"], r["name"]))[:150]


@router.get("/directory")
def directory(latitude: float = Query(13.086027, ge=-85, le=85, allow_inf_nan=False),
              longitude: float = Query(77.641252, ge=-180, le=180, allow_inf_nan=False),
              radius_km: int = Query(15, ge=1, le=30), discover: bool = False):
    key, stamp = (round(latitude, 5), round(longitude, 5), radius_km), time.time()
    with _lock:
        cached = _cache.get(key)
    snapshot_id = ":".join(map(str, key))
    if not cached:
        with db.connect() as conn:
            saved_snapshot = db.get(conn, "directory_snapshots", snapshot_id)
        if saved_snapshot:
            cached = (saved_snapshot["timestamp"], saved_snapshot["places"], saved_snapshot["fetched_at"])
    status, places, fetched_at = "not_requested", [], None
    if cached:
        status, places, fetched_at = "cached" if stamp-cached[0] <= 3600 else "stale", cached[1], cached[2]
    if discover and (not cached or stamp-cached[0] > 3600):
        around = f"(around:{radius_km*1000},{latitude},{longitude})"
        query = f'[out:json][timeout:20];(nwr["office"="ngo"]{around};nwr["amenity"="social_facility"]{around};nwr["recycling:organic"="yes"]{around};);out center tags;'
        try:
            places = parse_places(fetch_places(query), latitude, longitude, radius_km)
            status, fetched_at = "live", db.now()
            with _lock:
                if len(_cache) >= 64:
                    _cache.pop(next(iter(_cache)))
                _cache[key] = (stamp, places, fetched_at)
            with db.connect(write=True) as conn:
                db.put(conn, "directory_snapshots", {"id": snapshot_id, "timestamp": stamp, "places": places, "fetched_at": fetched_at})
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            status = "stale" if cached else "unavailable"
    with db.connect() as conn:
        saved = db.all_objects(conn, "recipients")
    contacts = CONTACTS if distance_km(latitude, longitude, 13.086027, 77.641252) < 50 else []
    return {"status": status, "places": places, "contacts": contacts, "saved": saved, "fetched_at": fetched_at,
            "radius_km": radius_km, "location": {"latitude": latitude, "longitude": longitude},
            "coverage": "OpenStreetMap coverage is incomplete. Distance is straight-line, not driving time. A listing is not acceptance or a partnership."}


class RecipientRequest(StrictModel):
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=5, max_length=400)
    contact: str = Field(min_length=5, max_length=200)
    source_url: str = Field(default="", max_length=500)
    latitude: float | None = Field(default=None, ge=-85, le=85)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    category: Literal["food_bank", "food_rescue_network", "ngo", "social_facility", "soup_kitchen", "organic_processor"] = "ngo"
    @field_validator("name", "address", "contact")
    @classmethod
    def strip_text(cls, value):
        if not value.strip():
            raise ValueError("A nonblank value is required")
        return value.strip()
    @model_validator(mode="after")
    def valid_location(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both coordinates, or leave both blank")
        if self.source_url and not safe_url(self.source_url):
            raise ValueError("Source must be an HTTP(S) URL")
        return self


@router.post("")
def save_recipient(request: RecipientRequest):
    result = {"id": db.identifier("recipient"), **request.model_dump(), "created_at": db.now(),
              "acceptance_status": "contact_required", "source": "Staff-maintained directory"}
    with db.connect(write=True) as conn:
        db.put(conn, "recipients", result)
    return result


class AcceptanceRequest(StrictModel):
    recipient_id: str
    batch_id: str
    route: Literal["human_redistribution", "compost", "biogas"]
    quantity_kg: float = Field(gt=0, le=1000000)
    confirmed_by: str = Field(min_length=2, max_length=100)
    contact_person: str = Field(min_length=2, max_length=100)
    evidence: str = Field(min_length=10, max_length=1000)
    expires_at: datetime
    @field_validator("confirmed_by", "contact_person", "evidence")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Document the contact and acceptance")
        return value.strip()


@router.post("/acceptances")
def accept(request: AcceptanceRequest):
    expiry = request.expires_at
    if expiry.tzinfo is None or not datetime.now(timezone.utc) < expiry <= datetime.now(timezone.utc)+timedelta(hours=24):
        raise DomainError("invalid_acceptance_expiry", "Acceptance must expire within 24 hours and include its timezone.")
    with db.connect(write=True) as conn:
        recipient, batch = db.get(conn, "recipients", request.recipient_id), db.get(conn, "batches", request.batch_id)
        if not recipient or not batch:
            raise DomainError("not_found", "Recipient or batch not found", 404)
        if request.route == "human_redistribution" and batch["origin"] != "untouched_surplus":
            raise DomainError("recovery_blocked", "Plate waste and unknown origin cannot enter human redistribution.")
        if request.route != "human_redistribution" and recipient["category"] != "organic_processor":
            raise DomainError("processor_required", "Select a documented organic processor for this route.")
        if batch["origin"] == "unknown":
            raise DomainError("unknown_origin", "Document the material category first.")
        result = {"id": db.identifier("acceptance"), **request.model_dump(mode="json"), "origin": batch["origin"],
                  "batch_quantity_kg": batch["quantity_kg"], "confirmed_at": db.now(), "label": "Staff-recorded recipient acceptance; not independent verification"}
        db.put(conn, "acceptances", result)
        return result


@router.get("/acceptances")
def acceptances():
    with db.connect() as conn:
        handoffs = db.all_objects(conn, "handoffs")
        return [{**a, "remaining_kg": max(0, a["quantity_kg"]-sum(h["quantity_kg"] for h in handoffs if h.get("acceptance_id") == a["id"])),
                 "expired": datetime.fromisoformat(a["expires_at"]) <= datetime.now(timezone.utc)} for a in db.all_objects(conn, "acceptances")]


@router.get("/dispatch")
def dispatches():
    with db.connect() as conn:
        return [h for h in db.all_objects(conn, "handoffs") if not h.get("simulated", True)]


class DispatchRequest(StrictModel):
    acceptance_id: str
    quantity_kg: float = Field(gt=0, le=1000000)
    received_by: str = Field(min_length=2, max_length=100)
    receipt_reference: str = Field(min_length=3, max_length=200)
    handoff_occurred: Literal[True]
    segregation_confirmed: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=100)
    @field_validator("received_by", "receipt_reference")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Receipt and receiver are required")
        return value.strip()


def register(app, batch_view, audit):
    @router.post("/dispatch")
    def dispatch(request: DispatchRequest):
        with db.connect(write=True) as conn:
            acceptance = db.get(conn, "acceptances", request.acceptance_id)
            if not acceptance:
                raise DomainError("not_found", "Acceptance not found", 404)
            batch = db.get(conn, "batches", acceptance["batch_id"])
            if not batch:
                raise DomainError("not_found", "Batch no longer exists", 404)
            # Idempotent retries return the committed immutable receipt, without another allocation.
            previous = next((h for h in db.all_objects(conn, "handoffs") if h["idempotency_key"] == request.idempotency_key), None)
            if previous:
                if previous.get("dispatch_intent") != request.model_dump():
                    raise DomainError("idempotency_conflict", "Key already used for another receipt", 409)
                return {**previous, "duplicate": True}
            if acceptance["origin"] != batch["origin"] or acceptance["batch_quantity_kg"] != batch["quantity_kg"]:
                raise DomainError("stale_acceptance", "Batch changed; confirm recipient acceptance again.", 409)
            if datetime.fromisoformat(acceptance["expires_at"]) <= datetime.now(timezone.utc):
                raise DomainError("acceptance_expired", "Obtain current recipient acceptance.")
            record = db.get(conn, "records", batch["record_id"])
            if not record or record["source"] != "measured":
                raise DomainError("measured_record_required", "Real dispatch requires measured kitchen records. Generated or unverified records support practice only.")
            if acceptance["route"] == "human_redistribution":
                state, reason = domain.review_state(batch)
                if state != "eligible_pending_approval" or not batch.get("approved_at"):
                    raise DomainError("recovery_blocked", reason if state != "eligible_pending_approval" else "Manager approval required.")
            elif batch["origin"] == "unknown":
                raise DomainError("unknown_origin", "Unknown material cannot be dispatched.")
            used = sum(h["quantity_kg"] for h in db.all_objects(conn, "handoffs") if h.get("acceptance_id") == acceptance["id"])
            if request.quantity_kg > min(acceptance["quantity_kg"]-used, batch_view(conn, batch)["remaining_kg"])+1e-9:
                raise DomainError("handoff_exceeded", "Receipt exceeds accepted capacity or remaining batch mass.")
            result = {"id": db.identifier("dispatch"), "acceptance_id": acceptance["id"], "batch_id": batch["id"],
                      "partner_id": acceptance["recipient_id"], "route": acceptance["route"], "quantity_kg": request.quantity_kg,
                      "idempotency_key": request.idempotency_key, "simulated": False, "recorded_at": db.now(),
                      "approved_at": batch.get("approved_at"), "reviewed_at": batch.get("reviewed_at"),
                      "dispatch_intent": request.model_dump(), "recipient_snapshot": db.get(conn, "recipients", acceptance["recipient_id"]),
                      "acceptance_snapshot": acceptance, "label": "Staff-recorded completed handoff; receipt evidence retained"}
            db.put(conn, "handoffs", result)
            audit(conn, "measured_handoff_recorded", batch["id"], result)
            return {**result, "duplicate": False}
    app.include_router(router)
