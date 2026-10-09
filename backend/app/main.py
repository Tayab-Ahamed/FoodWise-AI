import csv
import hashlib
import io
import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .config import load_local_env

load_local_env()

from . import db, domain, research
from .schemas import (ActualRequest, ApproveRequest, BatchRequest, CHECKS, CommitRequest,
                      ForecastRequest, HandoffRequest, PlanRequest, Record, ReportRequest,
                      ResetRequest, ReviewRequest, SimulationRequest, OptimizationRequest, TrialRequest)


from .errors import DomainError
from . import circular, recipes, station, recipients, intelligence, advisor


@asynccontextmanager
async def lifespan(app):
    db.bootstrap()
    yield


app = FastAPI(title="FoodWise AI", version="1.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origins=os.getenv("FOODWISE_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])


@app.exception_handler(DomainError)
async def domain_error(request, exc):
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message, "details": exc.details})


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={"code": "invalid_request", "message": "Please correct the highlighted values.",
                                                "details": [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]})


def require(conn, table, id):
    obj = db.get(conn, table, id)
    if obj is None:
        raise DomainError("not_found", f"{table.rstrip('s').capitalize()} not found", 404)
    return obj


def audit(conn, action, entity_id, details):
    db.put(conn, "audit", {"id": db.identifier("event"), "action": action, "entity_id": entity_id,
                           "details": details, "timestamp": db.now()})


def available_mass(conn, batch, exclude_id=None):
    record = require(conn, "records", batch["record_id"])
    if batch["origin"] == "unknown":
        raise DomainError("unknown_origin", "Select a documented category before allocating food.")
    field = "untouched_surplus_kg" if batch["origin"] == "untouched_surplus" else "plate_waste_kg"
    batches = db.all_objects(conn, "batches")
    allocated = sum(b["quantity_kg"] for b in batches
                    if b["record_id"] == batch["record_id"] and b["origin"] == batch["origin"] and b["id"] != exclude_id)
    return min(record[field] - allocated, unallocated_total(conn, batch["record_id"], exclude_id))


def unallocated_total(conn, record_id, exclude_id=None):
    record = require(conn, "records", record_id)
    allocated = sum(b["quantity_kg"] for b in db.all_objects(conn, "batches") if b["record_id"] == record_id and b["id"] != exclude_id)
    return record["untouched_surplus_kg"] + record["plate_waste_kg"] - allocated


def batch_view(conn, batch):
    handoffs = [h for h in db.all_objects(conn, "handoffs") if h["batch_id"] == batch["id"]]
    return {**batch, "handoffs": handoffs, "handed_off_kg": sum(h["quantity_kg"] for h in handoffs),
            "reuse_reserved_kg": circular.reserved_mass(conn, batch["id"]),
            "remaining_kg": max(0, batch["quantity_kg"] - sum(h["quantity_kg"] for h in handoffs) - circular.reserved_mass(conn, batch["id"]))}


@app.get("/api/health")
def health():
    with db.connect() as conn:
        return {"status": "ok", "explanation_mode": "deterministic", "dataset_version": db.version(conn),
                "dataset_source": conn.execute("SELECT value FROM meta WHERE key='dataset_source'").fetchone()[0],
                "demo_date": "2026-10-09", "synthetic_demo": any(r["source"] == "synthetic" for r in db.records(conn)),
                "practice_workspace": db.demo_enabled(), "default_ai_provider": "groq", "kitchen_timezone": "Asia/Kolkata"}


@app.get("/api/overview")
def overview(from_date: Annotated[date | None, Query(alias="from")] = None,
             to_date: Annotated[date | None, Query(alias="to")] = None):
    if from_date and to_date and from_date > to_date:
        raise DomainError("invalid_range", "Start date must be before end date")
    with db.connect() as conn:
        rows = [r for r in db.records(conn) if (not from_date or r["date"] >= str(from_date)) and (not to_date or r["date"] <= str(to_date))]
        result = domain.overview(rows)
        result.update(dataset_version=db.version(conn), dataset_source=conn.execute("SELECT value FROM meta WHERE key='dataset_source'").fetchone()[0])
        result["recorded_actual_count"] = conn.execute("SELECT count(*) FROM records WHERE kind='actual'").fetchone()[0]
        return result


@app.get("/api/records")
def records(ids: str | None = None):
    with db.connect() as conn:
        rows = db.records(conn)
        selected = set(ids.split(",")) if ids else None
        if selected is not None:
            active_ids = {r["record_id"] for r in rows}
            rows.extend({k: v for k, v in r.items() if k != "id"} for r in db.all_objects(conn, "archived_records") if r["record_id"] in selected and r["record_id"] not in active_ids)
        return [{**r, "served_kg": r["consumed_kg"] + r["plate_waste_kg"], "weekday": date.fromisoformat(r["date"]).strftime("%A")}
                for r in rows if selected is None or r["record_id"] in selected]


@app.get("/api/catalog")
def catalog():
    with db.connect() as conn:
        rows = db.records(conn)
        return {"items": sorted(set(r["item"] for r in rows)), "meal_items": {m: sorted(set(r["item"] for r in rows if r["meal"] == m)) for m in ["breakfast", "lunch", "dinner"]}}


@app.post("/api/datasets/preview")
async def preview(file: UploadFile = File(...)):
    data = await file.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        raise DomainError("file_too_large", "Maximum CSV upload is 5 MB")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")), strict=True)
        required = set(Record.model_fields) - {"display_qty", "display_unit", "piece_weight_kg", "source", "service_shortage_reported"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise DomainError("invalid_columns", "Missing required columns or duplicate headers", details=[{"field": "header", "message": "Required: " + ", ".join(sorted(required))}])
        errors, canonical, canonical_rows, seen = [], [], [], set()
        for number, row in enumerate(reader, 2):
            if number > 10001:
                raise DomainError("too_many_rows", "Maximum CSV upload is 10000 data rows")
            raw_id = (row.get("record_id") or "").strip()
            if raw_id and raw_id in seen:
                errors.append({"row": number, "field": "record_id", "message": "Duplicate record ID in upload"})
            seen.add(raw_id)
            try:
                if None in row:
                    raise ValueError("Row has extra columns")
                attendance = row.get("attendance", "")
                if not attendance or not attendance.isdecimal():
                    raise ValueError("attendance must be a positive integer")
                row["attendance"] = int(attendance)
                row["source"] = "user_provided_unverified"
                for field in ["display_qty", "display_unit", "piece_weight_kg", "service_shortage_reported"]:
                    if row.get(field) == "":
                        row.pop(field)
                record = Record.model_validate(row).model_dump(mode="json")
                canonical.append(record)
                canonical_rows.append(number)
            except ValidationError as exc:
                errors.extend({"row": number, "field": ".".join(map(str, e["loc"])) or "mass_balance", "message": e["msg"]} for e in exc.errors())
            except (ValueError, TypeError) as exc:
                errors.append({"row": number, "field": "row", "message": str(exc)})
        if not canonical and not errors:
            errors.append({"row": 2, "message": "CSV has no records"})
    except (UnicodeError, csv.Error) as exc:
        raise DomainError("invalid_csv", "CSV must be UTF-8 and well formed", details=[{"message": str(exc)}])
    with db.connect(write=True) as conn:
        existing = {r["record_id"] for r in db.records(conn)} | {r["record_id"] for r in db.all_objects(conn, "archived_records")}
        for number, record in zip(canonical_rows, canonical):
            if record["record_id"] in existing:
                errors.append({"row": number, "field": "record_id", "message": "Existing record ID conflicts. Use a new unique ID."})
        if errors:
            return {"valid": False, "errors": errors, "row_count": len(canonical), "preview": canonical[:10], "source": "user_provided_unverified"}
        token = db.identifier("preview")
        obj = {"id": token, "sha256": hashlib.sha256(data).hexdigest(), "records": canonical,
               "dataset_version": db.version(conn), "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()}
        db.put(conn, "previews", obj)
        return {"valid": True, "errors": [], "preview_token": token, "sha256": obj["sha256"], "row_count": len(canonical),
                "preview": canonical[:10], "source": "user_provided_unverified", "expires_at": obj["expires_at"]}


@app.post("/api/datasets/commit")
def commit(request: CommitRequest):
    with db.connect(write=True) as conn:
        obj = require(conn, "previews", request.preview_token)
        if datetime.fromisoformat(obj["expires_at"]) < datetime.now(timezone.utc):
            raise DomainError("preview_expired", "Preview expired. Preview the CSV again.", 409)
        if obj["dataset_version"] != db.version(conn):
            raise DomainError("stale_preview", "Dataset changed. Preview the CSV again.", 409)
        history_ids = {r[0] for r in conn.execute("SELECT id FROM records WHERE kind='history'")}
        if any(b["record_id"] in history_ids for b in db.all_objects(conn, "batches")):
            raise DomainError("linked_recovery", "Historical records have recovery allocations. Reset the demo before replacing this history.", 409)
        # The complete canonical file was validated before this single transaction.
        for row in conn.execute("SELECT id,payload FROM records WHERE kind='history'").fetchall():
            db.put(conn, "archived_records", {**db.payload(row), "id": row["id"]})
        conn.execute("DELETE FROM records WHERE kind='history'")
        for row in obj["records"]:
            conn.execute("INSERT INTO records(id,kind,plan_id,payload) VALUES (?,'history',NULL,?)", (row["record_id"], json.dumps(row, allow_nan=False)))
        conn.execute("DELETE FROM previews WHERE id=?", (request.preview_token,))
        conn.execute("UPDATE meta SET value='user_provided_unverified' WHERE key='dataset_source'")
        version = db.bump(conn)
        audit(conn, "dataset_replaced", request.preview_token, {"rows": len(obj["records"]), "sha256": obj["sha256"], "dataset_version": version})
        return {"imported_rows": len(obj["records"]), "dataset_version": version, "source": "user_provided_unverified"}


@app.post("/api/forecast")
def forecast(request: ForecastRequest):
    if len(set(request.items)) != len(request.items) or any(not i.strip() for i in request.items):
        raise DomainError("invalid_items", "Select distinct, nonblank items")
    with db.connect(write=True) as conn:
        df = domain.frame(db.records(conn))
        result = {"id": db.identifier("forecast"), "dataset_version": db.version(conn), "assumptions": request.model_dump(mode="json"),
                  "created_at": db.now(), "items": [domain.forecast_item(df, request, item) for item in request.items]}
        db.put(conn, "forecasts", result)
        return result


@app.post("/api/simulate")
def simulate(request: SimulationRequest):
    with db.connect() as conn:
        snapshot = require(conn, "forecasts", request.forecast_id)
        item = next((i for i in snapshot["items"] if i["item"] == request.item), None)
        if not item or item["status"] != "ready":
            raise DomainError("insufficient_data", "Simulation needs at least 5 prior records. Manual quantity has no projected outcomes.")
        return domain.simulate(item["demand_samples_kg"], request.quantity_kg, request.baseline_prepared_kg, item["cost_per_kg"], item["demand_kg"])


@app.post("/api/plans")
def plan(request: PlanRequest):
    with db.connect(write=True) as conn:
        snapshot = require(conn, "forecasts", request.forecast_id)
        if snapshot["dataset_version"] != db.version(conn):
            raise DomainError("stale_forecast", "New observations are available. Recalculate before approving.", 409)
        if set(request.quantities) != set(snapshot["assumptions"]["items"]):
            raise DomainError("invalid_quantities", "Supply a cooked quantity for every forecast item, including manual quantities for sparse history.")
        decisions = {}
        for item, decision_id in request.decision_ids.items():
            decision = require(conn, "decisions", decision_id)
            if (item not in request.quantities or decision["assumptions"]["forecast_id"] != snapshot["id"]
                    or decision["assumptions"]["item"] != item or decision["status"] != "ready"
                    or abs(decision["selected"]["quantity_kg"] - request.quantities[item]) > 1e-8):
                raise DomainError("decision_mismatch", "An optimization decision must match this forecast, item and approved quantity.")
            decisions[item] = decision
        coach = require(conn, "coach_reports", request.coach_id) if request.coach_id else None
        if coach and (coach["forecast_id"] != snapshot["id"] or coach["dataset_version"] != db.version(conn)):
            raise DomainError("coach_mismatch", "AI evidence must match the approved forecast and dataset.", 409)
        result = {"id": db.identifier("plan"), **request.model_dump(), "approved_at": db.now(), "dataset_version": db.version(conn),
                  "assumptions": snapshot["assumptions"], "decisions": decisions, "ai_evidence": coach,
                  "manual_items": [i["item"] for i in snapshot["items"] if i["status"] != "ready"]}
        db.put(conn, "plans", result)
        audit(conn, "plan_approved", result["id"], {"approved_by": request.approved_by, "quantities": request.quantities})
        return result


@app.get("/api/plans")
def plans():
    with db.connect() as conn:
        return db.all_objects(conn, "plans")


@app.post("/api/optimize")
def optimize(request: OptimizationRequest):
    with db.connect(write=True) as conn:
        snapshot = require(conn, "forecasts", request.forecast_id)
        if snapshot["dataset_version"] != db.version(conn):
            raise DomainError("stale_forecast", "New observations are available. Recalculate before optimizing.", 409)
        item = next((i for i in snapshot["items"] if i["item"] == request.item), None)
        if not item or item["status"] != "ready":
            raise DomainError("insufficient_data", "Optimization needs at least 5 prior served-food observations.")
        quality = item.get("data_quality", {})
        if quality.get("confirmed_shortage_ids"):
            raise DomainError("censored_demand", "Sample contains confirmed service shortages. Observed served food cannot reveal unmet demand; use a manager-reviewed manual quantity.",
                              details=[{"field": "service_shortage_reported", "message": "Confirmed shortage in record " + id} for id in quality["confirmed_shortage_ids"]])
        result = {"id": db.identifier("decision"), "created_at": db.now(), "dataset_version": snapshot["dataset_version"],
                  "assumptions": request.model_dump(), "history_ids": item["history_ids"], "data_quality": quality,
                  **research.optimize(item["demand_samples_kg"], request)}
        db.put(conn, "decisions", result)
        return result


def evaluate_trial(conn, trial):
    rows = [db.payload(r) for r in conn.execute("SELECT payload FROM records WHERE kind=?", (trial["record_scope"],))]
    return {**research.trial_evaluation(rows, trial), "dataset_version": db.version(conn)}


@app.post("/api/trials")
def create_trial(request: TrialRequest):
    if request.mode == "planned_trial" and request.record_scope != "actual":
        raise DomainError("trial_scope", "Planned trials use recorded actual meals. Historical rows are available only for labeled retrospective comparisons.")
    if request.mode == "planned_trial" and request.trial_start < date.fromisoformat(db.now()[:10]):
        raise DomainError("past_trial", "A new planned trial must start today or later. Use retrospective comparison for earlier windows.")
    with db.connect(write=True) as conn:
        trial = {"id": db.identifier("trial"), **request.model_dump(mode="json"), "approved_at": db.now()}
        db.put(conn, "trials", trial)
        audit(conn, "portion_trial_registered", trial["id"], {"approved_by": request.approved_by, "mode": request.mode})
        return evaluate_trial(conn, trial)


@app.get("/api/trials")
def trials():
    with db.connect() as conn:
        return [evaluate_trial(conn, t) for t in db.all_objects(conn, "trials")]


@app.post("/api/actuals/validate")
def validate_actuals(request: ActualRequest):
    return {"valid": True, "rows": [{"record_id": r.record_id, "served_kg": r.consumed_kg + r.plate_waste_kg,
                                     "balance_difference_kg": r.prepared_kg - r.consumed_kg - r.untouched_surplus_kg - r.plate_waste_kg} for r in request.records]}


@app.post("/api/actuals")
def actuals(request: ActualRequest):
    with db.connect(write=True) as conn:
        if len({r.record_id for r in request.records}) != len(request.records):
            raise DomainError("duplicate_id", "Duplicate IDs within actual meal entry", 409)
        plan = require(conn, "plans", request.plan_id) if request.plan_id else None
        if plan:
            circular.validate_actual_use(conn, plan, request.records)
            if any(r.date.isoformat() != plan["assumptions"]["date"] or r.meal != plan["assumptions"]["meal"] or r.item not in plan["quantities"] for r in request.records):
                raise DomainError("plan_mismatch", "Linked actuals must match the plan's date, meal and items.")
            existing_items = {db.payload(r)["item"] for r in conn.execute("SELECT payload FROM records WHERE kind='actual' AND plan_id=?", (request.plan_id,))}
            incoming = [r.item for r in request.records]
            if len(set(incoming)) != len(incoming) or existing_items.intersection(incoming):
                raise DomainError("duplicate_plan_item", "This plan item already has an actual record.", 409)
        for r in request.records:
            if db.get(conn, "records", r.record_id) or db.get(conn, "archived_records", r.record_id):
                raise DomainError("duplicate_id", f"Record {r.record_id} already exists", 409)
        for r in request.records:
            conn.execute("INSERT INTO records(id,kind,plan_id,payload) VALUES (?,'actual',?,?)", (r.record_id, request.plan_id, r.model_dump_json()))
        if plan:
            circular.complete_actual_use(conn, plan, request.records)
        version = db.bump(conn)
        if conn.execute("SELECT value FROM meta WHERE key='dataset_source'").fetchone()[0] == "empty":
            sources = sorted({r.source for r in request.records})
            conn.execute("UPDATE meta SET value=? WHERE key='dataset_source'", (sources[0] if len(sources) == 1 else "mixed",))
        audit(conn, "actual_meal_recorded", request.plan_id or "unplanned", {"record_ids": [r.record_id for r in request.records], "dataset_version": version})
        return {"record_ids": [r.record_id for r in request.records], "dataset_version": version,
                "rows": [{"record_id": r.record_id, "served_kg": r.consumed_kg + r.plate_waste_kg} for r in request.records]}


@app.get("/api/investigations")
def investigations():
    with db.connect() as conn:
        return domain.investigations(db.records(conn))


@app.get("/api/inventory")
def inventory(as_of: date = date(2026, 10, 9), near_days: int = Query(default=2, ge=0, le=30)):
    with db.connect() as conn:
        rows = []
        for r in db.all_objects(conn, "inventory"):
            delta = (date.fromisoformat(r["expiry_date"]) - as_of).days
            state = "expired" if delta < 0 else "due_today" if delta == 0 else "near_expiry" if delta <= near_days else "later"
            if delta < 0 and r.get("label_kind") == "best_before":
                state = "past_best_before"
            rows.append({**r, "days_until_expiry": delta, "status": state,
                         **recipes.eligibility(r, as_of),
                         "warning": ("Past best-before: quality review required; excluded from recipe planning" if r.get("label_kind") == "best_before" else "Expired or unclassified label — do not use") if delta < 0 else "Label date warning only; verify storage and kitchen policy.",
                         "storage_status": "verified by staff" if r["storage_verified"] is True else "unknown or unverified; review required"})
        return {"as_of": str(as_of), "near_days": near_days, "items": rows, "units": "raw ingredient kg; separate from cooked meal kg"}


@app.post("/api/recovery/batches")
def create_batch(request: BatchRequest):
    with db.connect(write=True) as conn:
        batch = {"id": db.identifier("batch"), **request.model_dump(), "checks": {k: None for k in CHECKS},
                 "reviewer": None, "reviewed_at": None, "approved_by": None, "approved_at": None, "created_at": db.now()}
        require(conn, "records", batch["record_id"])
        if batch["origin"] == "unknown":
            record = require(conn, "records", batch["record_id"])
            if batch["quantity_kg"] > unallocated_total(conn, batch["record_id"]) + 1e-9:
                raise DomainError("allocation_exceeded", "Unknown-origin quantity cannot exceed recorded waste mass; it is blocked from all routes until classified.")
        elif batch["quantity_kg"] > available_mass(conn, batch) + 1e-9:
            raise DomainError("allocation_exceeded", "Batch exceeds unallocated cooked mass in this record/category")
        batch["state"], batch["reason"] = domain.review_state(batch)
        db.put(conn, "batches", batch)
        audit(conn, "batch_created", batch["id"], {"state": batch["state"], "origin": batch["origin"]})
        return batch_view(conn, batch)


@app.get("/api/recovery/batches")
def batches():
    with db.connect() as conn:
        return [batch_view(conn, b) for b in db.all_objects(conn, "batches")]


@app.patch("/api/recovery/batches/{id}")
def change_batch(id: str, request: BatchRequest):
    with db.connect(write=True) as conn:
        batch = require(conn, "batches", id)
        if any(h["batch_id"] == id for h in db.all_objects(conn, "handoffs")):
            raise DomainError("handoff_exists", "Cannot change mass/origin after recorded disposition. Create a new batch for unallocated food.", 409)
        if circular.reserved_mass(conn, id) > 0:
            raise DomainError("reuse_exists", "Reject active reuse plans before changing a batch. Completed reuse is immutable.", 409)
        circular.invalidate(conn, id, "Batch quantity or origin changed")
        revised = {**batch, **request.model_dump()}
        revised.pop("reuse_evidence", None)
        require(conn, "records", revised["record_id"])
        if revised["quantity_kg"] > unallocated_total(conn, revised["record_id"], id) + 1e-9:
            raise DomainError("allocation_exceeded", "Batch exceeds remaining recorded surplus and plate-waste mass")
        if revised["origin"] != "unknown" and revised["quantity_kg"] > available_mass(conn, revised, id) + 1e-9:
            raise DomainError("allocation_exceeded", "Batch exceeds unallocated category mass")
        revised.update(approved_by=None, approved_at=None, reviewer=None, reviewed_at=None, checks={k: None for k in CHECKS})
        revised["state"], revised["reason"] = domain.review_state(revised)
        db.put(conn, "batches", revised)
        audit(conn, "batch_changed_approval_invalidated", id, request.model_dump())
        return batch_view(conn, revised)


@app.patch("/api/recovery/batches/{id}/review")
def review(id: str, request: ReviewRequest):
    with db.connect(write=True) as conn:
        batch = require(conn, "batches", id)
        circular.invalidate(conn, id, "Handling review changed; renewed approval required")
        batch.update(checks={k: getattr(request, k) for k in CHECKS}, reviewer=request.reviewer,
                     reviewed_at=db.now(), approved_by=None, approved_at=None)
        batch["state"], batch["reason"] = domain.review_state(batch)
        db.put(conn, "batches", batch)
        audit(conn, "review_saved_approval_invalidated", id, {"reviewer": request.reviewer, "checks": batch["checks"], "state": batch["state"]})
        return batch_view(conn, batch)


@app.post("/api/recovery/batches/{id}/approve")
def approve(id: str, request: ApproveRequest):
    with db.connect(write=True) as conn:
        batch = require(conn, "batches", id)
        state, reason = domain.review_state(batch)
        if state != "eligible_pending_approval":
            raise DomainError("recovery_blocked", reason)
        circular.invalidate(conn, id, "Batch approval renewed; obtain a new reuse proposal")
        batch.update(state="approved_for_simulated_handoff" if db.demo_enabled() else "approved_pending_recipient_acceptance", approved_by=request.approved_by, approved_at=db.now(), reason="Manager review approved; recipient acceptance and documented handoff remain required. Not food-safety certification.")
        db.put(conn, "batches", batch)
        audit(conn, "recovery_approved", id, request.model_dump())
        return batch_view(conn, batch)


PARTNERS = [
    {"id": "demo-community", "name": "Demo community handoff", "demo": True, "routes": ["human_redistribution"], "accepts": ["untouched_surplus"]},
    {"id": "demo-compost", "name": "Demo compost processor", "demo": True, "routes": ["compost"], "accepts": ["untouched_surplus", "plate_waste"]},
    {"id": "demo-biogas", "name": "Demo biogas processor", "demo": True, "routes": ["biogas"], "accepts": ["untouched_surplus", "plate_waste"]},
    {"id": "demo-unconfirmed", "name": "Demo processor — acceptance unknown", "demo": True, "routes": ["compost"], "accepts": []},
]


@app.get("/api/recovery/partners")
def partners():
    return PARTNERS


@app.post("/api/recovery/batches/{id}/handoff")
def handoff(id: str, request: HandoffRequest):
    if not db.demo_enabled():
        raise DomainError("practice_disabled", "Use recipient acceptance and the measured dispatch ledger in operations mode.", 409)
    with db.connect(write=True) as conn:
        batch = require(conn, "batches", id)
        # Even a retry is rechecked against current evidence, before returning the receipt.
        eligibility, reason = domain.review_state(batch)
        if request.route == "human_redistribution" and (eligibility != "eligible_pending_approval" or not batch.get("approved_at")):
            raise DomainError("recovery_blocked", reason if eligibility != "eligible_pending_approval" else "Manager approval required")
        partner = next((p for p in PARTNERS if p["id"] == request.partner_id), None)
        if not partner or not partner["demo"] or request.route not in partner["routes"] or batch["origin"] not in partner["accepts"]:
            raise DomainError("processor_acceptance_required", "Disposal review required: demo processor acceptance for this material/route is unknown.")
        previous = next((h for h in db.all_objects(conn, "handoffs") if h["idempotency_key"] == request.idempotency_key), None)
        if previous:
            if previous["batch_id"] != id or any(previous[k] != getattr(request, k) for k in ["route", "partner_id", "quantity_kg"]):
                raise DomainError("idempotency_conflict", "Idempotency key was used for a different handoff", 409)
            if previous.get("segregation_confirmed") != request.segregation_confirmed or previous.get("biogas_assumptions") != (request.biogas_assumptions.model_dump() if request.biogas_assumptions else None):
                raise DomainError("idempotency_conflict", "Receipt assumptions cannot change on retry", 409)
            return {**previous, "duplicate": True}
        remaining = batch_view(conn, batch)["remaining_kg"]
        if request.quantity_kg > remaining + 1e-9:
            raise DomainError("handoff_exceeded", "Split handoffs cannot exceed remaining batch mass")
        result = {"id": db.identifier("handoff"), "batch_id": id, **request.model_dump(), "simulated": True,
                  "recorded_at": db.now(), "approved_at": batch.get("approved_at"), "reviewed_at": batch.get("reviewed_at")}
        if request.biogas_assumptions is not None:
            if request.route != "biogas" or request.segregation_confirmed is not True:
                raise DomainError("segregation_required", "Biogas potential requires a biogas route and confirmed segregation")
            result["potential"] = circular.biogas_potential(request.quantity_kg, request.biogas_assumptions.model_dump())
        db.put(conn, "handoffs", result)
        if request.route == "human_redistribution":
            batch["state"] = "simulated_handoff_recorded"
        batch["reason"] = "Simulated disposition recorded; no real partner contacted."
        db.put(conn, "batches", batch)
        audit(conn, "simulated_handoff_recorded", id, result)
        return {**result, "duplicate": False}


@app.get("/api/audit")
def activity():
    with db.connect() as conn:
        return db.all_objects(conn, "audit")


def report_evidence(conn, snapshot, plan=None):
    items = []
    for item in snapshot["items"]:
        evidence = {"item": item["item"], "history_ids": item["history_ids"], "sample_count": item["sample_count"], "fallback_reason": item["fallback_reason"], "backtest": item["backtest"], "data_quality": item.get("data_quality", {})}
        if item["status"] == "ready":
            q = plan["quantities"][item["item"]] if plan else item["recommended_kg"]
            evidence.update(demand_kg=item["demand_kg"], quantity_kg=q, range_low_kg=item["range_low_kg"], range_high_kg=item["range_high_kg"],
                            simulation=domain.simulate(item["demand_samples_kg"], q, item["baseline_prepared_kg"], item["cost_per_kg"], item["demand_kg"]))
        items.append(evidence)
    return {"forecast_id": snapshot["id"], "dataset_version": snapshot["dataset_version"], "assumptions": snapshot["assumptions"],
            "reuse": db.get(conn, "reuse_plans", plan["reuse_id"]) if plan and plan.get("reuse_id") else None,
            "optimization_decisions": plan.get("decisions", {}) if plan else {},
            "plan_id": plan["id"] if plan else None, "approved_by": plan["approved_by"] if plan else None, "items": items}


@app.post("/api/report")
def report(request: ReportRequest):
    with db.connect() as conn:
        snapshot = require(conn, "forecasts", request.forecast_id)
        plan = require(conn, "plans", request.plan_id) if request.plan_id else None
        if plan and plan["forecast_id"] != snapshot["id"]:
            raise DomainError("plan_mismatch", "Plan belongs to a different forecast")
        evidence = report_evidence(conn, snapshot, plan)
        lines = [f"Dataset version {snapshot['dataset_version']}; expected attendance {snapshot['assumptions']['expected_attendance']} for {snapshot['assumptions']['date']} {snapshot['assumptions']['meal']}. Forecasts target food served, including plate waste."]
        if evidence["reuse"]:
            reuse = evidence["reuse"]
            lines.append(f"Dinner reuse {reuse['id']}, state {reuse['state']}, source {reuse['source']}: {reuse['dinner_total_kg']:.2f} kg total dinner food comprises {reuse['fresh_preparation_kg']:.2f} kg planned fresh preparation plus {reuse['quantity_kg']:.2f} kg reserved reuse from lunch record {reuse['lunch_record_id']}. {reuse['demand_basis']}. Holding evidence SHA-256 {reuse['evidence_sha256']}. This transfer is not additional food, measured waste prevention, food-safety certification or realized savings. Only a completed linked actual records use.")
        for item in evidence["items"]:
            if "demand_kg" not in item:
                lines.append(f"{item['item']}: insufficient history. {item['fallback_reason']}")
                continue
            sim = item["simulation"]
            lines.append(f"{item['item']}: served demand {item['demand_kg']:.1f} kg from {item['sample_count']} prior records. At {item['quantity_kg']:.1f} kg preparation, projected surplus is {sim['expected_surplus_kg']:.1f} kg and shortage {sim['expected_shortage_kg']:.1f} kg. Historical shortage frequency {sim['shortage_frequency']:.1%}. Evidence: {', '.join(item['history_ids'])}. {item['fallback_reason'] or 'Weekday and event matched.'}")
            quality = item["data_quality"]
            if quality.get("confirmed_shortage_ids"):
                lines.append(f"{item['item']}: confirmed shortages in {', '.join(quality['confirmed_shortage_ids'])}; served food may understate desired demand. Cost optimization is blocked for this sample; a manager-reviewed quantity cannot be treated as a lost-demand estimate.")
            if quality.get("shortage_unknown_count"):
                lines.append(f"{item['item']}: shortage status was not logged for {quality['shortage_unknown_count']} sample observations. Missing status means unknown, not no shortage.")
        lines.append("Historical ranges are descriptive, not calibrated confidence intervals. Review shortage exposure before approval. Try smaller first servings separately for plate waste. Untouched surplus needs documented review and manager approval; plate waste cannot enter human redistribution. Projected effects are not measured savings.")
        for item, decision in evidence["optimization_decisions"].items():
            assumptions = decision["assumptions"]
            lines.append(f"{item}: manager adopted empirical cost-aware quantity {decision['selected']['quantity_kg']:.2f} kg. Scenario penalties: surplus ₹{assumptions['surplus_cost_per_kg']:.2f}/kg and shortage ₹{assumptions['shortage_cost_per_kg']:.2f}/kg; capacity {assumptions['capacity_kg']:.2f} kg; maximum historical shortage frequency {assumptions['max_shortage_frequency']:.1%}. Projected scenario loss ₹{decision['selected']['scenario_loss_inr']:.2f}, not realized savings. Missing shortage flags are unknown; observed served food may understate latent demand.")
        return {"evidence": evidence, "explanation": "\n\n".join(lines), "explanation_mode": "deterministic", "generated_at": db.now()}


@app.get("/api/impact")
def impact():
    with db.connect() as conn:
        handoffs = db.all_objects(conn, "handoffs")
        recorded = [db.payload(r) for r in conn.execute("SELECT payload FROM records WHERE kind='actual'")]
        projections = []
        for plan in db.all_objects(conn, "plans"):
            if plan.get("reuse_id"):
                continue  # Reuse impact is separately reported; do not double-count projected prevention.
            snapshot = require(conn, "forecasts", plan["forecast_id"])
            evidence = report_evidence(conn, snapshot, plan)
            linked = [db.payload(r) for r in conn.execute("SELECT payload FROM records WHERE plan_id=?", (plan["id"],))]
            errors = []
            for r in linked:
                forecast_item = next(i for i in snapshot["items"] if i["item"] == r["item"])
                errors.append({"record_id": r["record_id"], "item": r["item"], "planned_kg": plan["quantities"][r["item"]],
                               "actual_prepared_kg": r["prepared_kg"], "actual_served_kg": r["consumed_kg"] + r["plate_waste_kg"],
                               "served_forecast_error_kg": r["consumed_kg"] + r["plate_waste_kg"] - forecast_item["demand_kg"] if forecast_item["status"] == "ready" else None})
            projections.append({"plan": plan, "evidence": evidence, "actual_comparison": errors,
                                "projected_untouched_difference_kg": sum(i["simulation"]["prevented_untouched_surplus_kg"] for i in evidence["items"] if "simulation" in i),
                                "projected_cost_difference_inr": sum(i["simulation"]["potential_cost_difference_inr"] for i in evidence["items"] if "simulation" in i)})
        return {"recorded_actuals": domain.overview(recorded), "plans": projections,
                "simulated_dispositions": {r: sum(h["quantity_kg"] for h in handoffs if h["route"] == r and h.get("simulated", True)) for r in ["human_redistribution", "compost", "biogas"]},
                "recorded_dispositions": {r: sum(h["quantity_kg"] for h in handoffs if h["route"] == r and not h.get("simulated", True)) for r in ["human_redistribution", "compost", "biogas"]},
                "caveat": "Actuals retain their source labels. Simulated recovery is separate from projected prevention. A before/after observation does not establish causal savings."}


@app.get("/api/demo/accounting")
def accounting_fixture():
    if not db.demo_enabled():
        raise DomainError("practice_disabled", "Accounting examples are disabled in the operations workspace.", 409)
    return db.load_csv(db.ROOT / "data" / "demo_accounting.csv")[0]


@app.post("/api/demo/reset")
def reset(request: ResetRequest):
    with db.connect(write=True) as conn:
        seeded = conn.execute("SELECT value FROM meta WHERE key='demo_seeded'").fetchone()
        if os.getenv("FOODWISE_DEMO", "true").lower() != "true" or not seeded or seeded[0] != "true":
            raise DomainError("reset_disabled", "Reset is only enabled in the seeded demo environment", 409)
        db.seed(conn)
        return {"message": "Synthetic history and inventory restored; plans, actuals and recovery cleared.", "dataset_version": db.version(conn)}


circular.register(app, require, audit, batch_view, PARTNERS)
recipes.register(app, require, audit)
app.include_router(station.router)
recipients.register(app, batch_view, audit)
app.include_router(intelligence.router)
app.include_router(advisor.router)
