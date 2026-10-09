"""Additive circular-kitchen workflow. No forecast algorithm or historical rows are changed."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json

from fastapi import APIRouter
from . import db, domain
from .errors import DomainError
from .schemas import BiogasAssumptions, BiogasEstimateRequest, ReuseDecision, ReuseEvidence, ReuseProposal

KITCHEN_TZ = timezone(timedelta(hours=5, minutes=30))
# Conservative demonstration gate, not a jurisdiction-specific HACCP procedure.
# The hot-holding floor follows FSA guidance; duration/gap are explicit demo assumptions.
POLICY = {"id": "same-day-hot-holding-demo-v1", "minimum_celsius": 63,
          "maximum_holding_hours": 6, "maximum_reading_gap_minutes": 60,
          "label": "Demo gate; qualified kitchen procedure review still required. Not safety certification.",
          "source": "https://www.food.gov.uk/safety-hygiene/cooking-your-food"}
RESERVED_STATES = {"pending", "approved", "completed"}


def reserved_mass(conn, batch_id):
    return sum(p["quantity_kg"] for p in db.all_objects(conn, "reuse_plans")
               if p["batch_id"] == batch_id and p["state"] in RESERVED_STATES)


def evidence_hash(batch):
    evidence = {k: batch.get(k) for k in ["record_id", "origin", "quantity_kg", "checks", "reviewer",
                                         "reviewed_at", "approved_at", "reuse_evidence"]}
    return hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()


def invalidate(conn, batch_id, reason):
    for p in db.all_objects(conn, "reuse_plans"):
        if p["batch_id"] == batch_id and p["state"] in {"pending", "approved"}:
            p.update(state="invalidated", invalidation_reason=reason, invalidated_at=db.now())
            db.put(conn, "reuse_plans", p)
            if p.get("plan_id"):
                plan = db.get(conn, "plans", p["plan_id"])
                plan["reuse_state"] = "invalidated"
                db.put(conn, "plans", plan)
            db.put(conn, "audit", {"id": db.identifier("event"), "action": "reuse_approval_invalidated",
                                   "entity_id": p["id"], "details": {"reason": reason}, "timestamp": db.now()})


def reuse_reasons(conn, batch):
    reasons = []
    row = conn.execute("SELECT kind,payload FROM records WHERE id=?", (batch["record_id"],)).fetchone()
    record = db.payload(row) if row else None
    if not record or row["kind"] != "actual" or record["meal"] != "lunch":
        reasons.append("Reuse requires a recorded lunch actual, not a historical training row.")
    if batch["origin"] != "untouched_surplus":
        reasons.append("Only untouched surplus can enter dinner reuse. Plate waste is permanently blocked.")
    if any(b["record_id"] == batch["record_id"] and b["origin"] == "unknown" for b in db.all_objects(conn, "batches")):
        reasons.append("Resolve unknown-origin allocations on this meal before reserving food for human use.")
    state, reason = domain.review_state(batch)
    if state != "eligible_pending_approval":
        reasons.append(reason)
    if not batch.get("approved_at"):
        reasons.append("A current documented review and manager batch approval are required.")
    e = batch.get("reuse_evidence")
    if not e:
        return reasons + ["Detailed holding and temperature evidence is missing."]
    if e["holding_mode"] != "hot_held":
        reasons.append("Only same-day documented hot holding is supported. Chilled, ambient and unknown modes are blocked.")
    for field in ["continuous_monitoring_verified", "procedure_allows_this_food", "protected_separate_container"]:
        if e.get(field) is not True:
            reasons.append(f"{field.replace('_', ' ')} must be explicitly passed; unknown or failed blocks reuse.")
    start = datetime.fromisoformat(e["holding_started_at"]) if e.get("holding_started_at") else None
    end = datetime.fromisoformat(e["dinner_service_at"]) if e.get("dinner_service_at") else None
    if not start or not end or not start.tzinfo or not end.tzinfo:
        return reasons + ["Timezone-aware holding start and dinner service times are required."]
    hours = (end - start).total_seconds() / 3600
    if not 0 < hours <= POLICY["maximum_holding_hours"]:
        reasons.append("Holding window must be ordered and no longer than the demo policy's 6 hours.")
    if record and (start.astimezone(KITCHEN_TZ).date().isoformat() != record["date"]
                   or end.astimezone(KITCHEN_TZ).date().isoformat() != record["date"]):
        reasons.append("Lunch holding and dinner service must fall on the recorded day in Asia/Kolkata.")
    readings = e["temperatures"]
    if len(readings) < 2:
        return reasons + ["Temperature log needs start/end coverage and readings at most 60 minutes apart."]
    points = []
    for reading in readings:
        at = datetime.fromisoformat(reading["at"])
        if not at.tzinfo:
            reasons.append("Every temperature reading needs a timezone.")
            continue
        points.append(at)
        if not POLICY["minimum_celsius"] <= reading["celsius"] <= 100:
            reasons.append("Temperature evidence fails the demo hot-holding gate (63–100 °C).")
    if len(points) == len(readings):
        if points != sorted(points) or len(set(points)) != len(points) or points[0] != start or points[-1] != end:
            reasons.append("Ordered, distinct temperature readings must exactly cover the entire holding window.")
        if any((b-a).total_seconds() > POLICY["maximum_reading_gap_minutes"] * 60 for a, b in zip(points, points[1:])):
            reasons.append("A temperature-log gap exceeds the demo 60-minute maximum.")
    return list(dict.fromkeys(reasons))


def assert_reusable(conn, batch, expected_hash=None):
    reasons = reuse_reasons(conn, batch)
    if expected_hash and evidence_hash(batch) != expected_hash:
        reasons.append("Evidence changed after the proposal; create a new proposal and obtain renewed approval.")
    if reasons:
        raise DomainError("reuse_blocked", "Dinner reuse blocked.", details=[{"message": r} for r in reasons])


def validate_actual_use(conn, plan, records):
    if not plan.get("reuse_id"):
        return
    reuse = db.get(conn, "reuse_plans", plan["reuse_id"])
    if reuse["state"] != "approved":
        raise DomainError("reuse_not_approved", "This dinner reuse plan is no longer approved or has already been recorded.", 409)
    batch = db.get(conn, "batches", reuse["batch_id"])
    assert_reusable(conn, batch, reuse["evidence_sha256"])
    if len(records) != 1 or records[0].item != reuse["item"]:
        raise DomainError("reuse_actual_mismatch", "Record the one compatible dinner dish for this reuse plan.")
    if records[0].prepared_kg + 1e-9 < reuse["quantity_kg"]:
        raise DomainError("reuse_actual_mismatch", "Total dinner food must include all reserved reuse kg. Reject the plan before revising its allocation.")
    if records[0].source != reuse["source"]:
        raise DomainError("reuse_source_mismatch", "Retain the lunch source label on the linked dinner; synthetic food cannot become measured evidence.")


def complete_actual_use(conn, plan, records):
    if plan.get("reuse_id"):
        p = db.get(conn, "reuse_plans", plan["reuse_id"])
        p.update(state="completed", outcome_record_id=records[0].record_id, completed_at=db.now(),
                 recorded_reused_kg=p["quantity_kg"], recorded_fresh_kg=records[0].prepared_kg-p["quantity_kg"],
                 outcome_label="Staff-recorded use, retaining source label; not independently verified")
        db.put(conn, "reuse_plans", p)
        plan["reuse_state"] = "completed"
        db.put(conn, "plans", plan)
        db.put(conn, "audit", {"id": db.identifier("event"), "action": "dinner_reuse_actual_recorded",
                               "entity_id": p["id"], "timestamp": db.now(),
                               "details": {"record_id": records[0].record_id, "recorded_reused_kg": p["quantity_kg"],
                                           "recorded_fresh_kg": p["recorded_fresh_kg"], "source": p["source"], "evidence_sha256": p["evidence_sha256"]}})


def biogas_potential(quantity, assumptions):
    gas = quantity * assumptions["gas_m3_per_kg_wet"]
    methane = gas * assumptions["methane_fraction"]
    chemical = methane * assumptions["methane_kwh_per_m3"]
    electricity = chemical * assumptions["electricity_efficiency"]
    heat = chemical * assumptions["heat_efficiency"]
    return {"wet_food_kg": quantity, "biogas_m3": gas, "methane_m3": methane,
            "chemical_energy_kwh": chemical, "electricity_kwh": electricity, "useful_heat_kwh": heat,
            "useful_energy_kwh": electricity+heat, "actual_measured_energy_kwh": None,
            "assumptions": assumptions, "label": "Illustrative theoretical potential, not measured energy",
            "caveat": "Assumed wet-food yield and conversion efficiencies; composition, gas conditions, contamination, digester losses and parasitic loads are not measured. No gas or electricity generation is recorded."}


def register(app, require, audit, batch_view, partners):
    # FastAPI APIRouter: https://fastapi.tiangolo.com/tutorial/bigger-applications/
    router = APIRouter(prefix="/api", tags=["Circular kitchen"])

    @router.get("/reuse/options")
    def options():
        with db.connect() as conn:
            batches = db.all_objects(conn, "batches")
            meals = []
            for row in conn.execute("SELECT payload FROM records WHERE kind='actual'"):
                r = db.payload(row)
                if r["meal"] == "lunch":
                    linked = [b for b in batches if b["record_id"] == r["record_id"]]
                    allocated = sum(b["quantity_kg"] for b in linked if b["origin"] == "untouched_surplus")
                    unknown = any(b["origin"] == "unknown" for b in linked)
                    total_remaining = r["untouched_surplus_kg"] + r["plate_waste_kg"] - sum(b["quantity_kg"] for b in linked)
                    meals.append({**r, "unallocated_untouched_kg": max(0, min(r["untouched_surplus_kg"]-allocated, total_remaining)),
                                  "unknown_allocations_block_reuse": unknown,
                                  "compatible_dinner_items": [r["item"]],
                                  "compatibility_note": "Same cooked dish only; no unvalidated transformation or raw-to-cooked yield."})
            return {"lunch_actuals": meals, "policy": POLICY,
                    "batches": [{**batch_view(conn, b), "reuse_blockers": reuse_reasons(conn, b)} for b in batches],
                    "label": "Staff-reviewed policy workflow, not food-safety certification"}

    @router.get("/reuse/batches/{id}/synthetic-example")
    def synthetic_example(id: str):
        with db.connect() as conn:
            b = require(conn, "batches", id)
            r = require(conn, "records", b["record_id"])
            if r["source"] != "synthetic" or b["origin"] != "untouched_surplus":
                raise DomainError("synthetic_only", "Example evidence is only available for synthetic untouched food. Enter real logs for other records.")
            start = datetime.fromisoformat(r["date"]+"T13:00:00+05:30")
            return {"procedure_reference": "SYNTHETIC-HOT-HOLD-DEMO; replace with kitchen procedure", "reviewer": "Demo reviewing staff",
                    "holding_mode": "hot_held", "holding_started_at": start.isoformat(),
                    "dinner_service_at": (start+timedelta(hours=6)).isoformat(),
                    "temperatures": [{"at": (start+timedelta(hours=h)).isoformat(), "celsius": 65} for h in range(7)],
                    "continuous_monitoring_verified": True, "procedure_allows_this_food": True, "protected_separate_container": True,
                    "notes": "Synthetic example log only; no real food was examined or held."}

    @router.patch("/reuse/batches/{id}/evidence")
    def evidence(id: str, request: ReuseEvidence):
        with db.connect(write=True) as conn:
            batch = require(conn, "batches", id)
            if batch["origin"] != "untouched_surplus":
                raise DomainError("reuse_blocked", "Plate waste and unknown origin cannot enter dinner reuse.")
            invalidate(conn, id, "Detailed holding evidence changed")
            batch["reuse_evidence"] = {**request.model_dump(mode="json"), "recorded_at": db.now(), "policy": POLICY}
            db.put(conn, "batches", batch)
            audit(conn, "reuse_evidence_saved", id, batch["reuse_evidence"])
            return {**batch_view(conn, batch), "reuse_blockers": reuse_reasons(conn, batch)}

    @router.post("/reuse/proposals")
    def propose(request: ReuseProposal):
        with db.connect(write=True) as conn:
            batch = require(conn, "batches", request.batch_id)
            assert_reusable(conn, batch)
            record = require(conn, "records", batch["record_id"])
            forecast = require(conn, "forecasts", request.dinner_forecast_id)
            if forecast["dataset_version"] != db.version(conn):
                raise DomainError("stale_forecast", "Recalculate dinner demand after new actuals.", 409)
            if (forecast["assumptions"]["meal"] != "dinner" or forecast["assumptions"]["date"] != record["date"]
                    or forecast["assumptions"]["items"] != [record["item"]] or request.compatibility_confirmed is not True):
                raise DomainError("incompatible_dinner", "Same-day dinner, the identical cooked dish, and explicit kitchen compatibility review are required.")
            item = forecast["items"][0]
            if item["status"] == "ready":
                if request.manual_dinner_total_kg is not None:
                    raise DomainError("manual_override", "This forecast has evidence. Use its recommendation, or create a regular manager-reviewed plan.")
                total, basis = item["recommended_kg"], "Historical served-food dinner forecast with buffer"
            else:
                if request.manual_dinner_total_kg is None:
                    raise DomainError("manual_demand_required", "Insufficient dinner history. A manager-entered total is required; no forecast is invented.")
                total, basis = request.manual_dinner_total_kg, "Manual dinner quantity; insufficient dinner history, no projected shortage estimate"
            if request.quantity_kg > min(total, batch_view(conn, batch)["remaining_kg"]) + 1e-9:
                raise DomainError("reuse_exceeded", "Reuse cannot exceed unreserved batch mass or total dinner quantity.")
            result = {"id": db.identifier("reuse"), **request.model_dump(), "state": "pending", "created_at": db.now(),
                      "item": record["item"], "source": record["source"], "lunch_record_id": record["record_id"],
                      "dinner_total_kg": total, "fresh_preparation_kg": total-request.quantity_kg, "demand_basis": basis,
                      "evidence_sha256": evidence_hash(batch), "policy": POLICY,
                      "label": "Reserved proposal, awaiting qualified manager approval; not realized savings"}
            db.put(conn, "reuse_plans", result)
            audit(conn, "dinner_reuse_reserved", result["id"], result)
            return result

    @router.post("/reuse/proposals/{id}/decision")
    def decision(id: str, request: ReuseDecision):
        with db.connect(write=True) as conn:
            p = require(conn, "reuse_plans", id)
            if p["state"] not in {"pending", "approved"}:
                raise DomainError("reuse_state", "Only an unused pending/approved proposal can be decided.", 409)
            if request.decision == "approve":
                if p["state"] == "approved":
                    raise DomainError("reuse_state", "Already approved. Its allocation is unchanged.", 409)
                if request.qualified_kitchen_manager is not True or request.procedure_review_confirmed is not True:
                    raise DomainError("qualified_manager_required", "Qualified kitchen manager and applicable procedure review must be explicitly attested.")
                batch = require(conn, "batches", p["batch_id"])
                assert_reusable(conn, batch, p["evidence_sha256"])
                snapshot = require(conn, "forecasts", p["dinner_forecast_id"])
                if snapshot["dataset_version"] != db.version(conn):
                    raise DomainError("stale_forecast", "New actuals require a new dinner proposal.", 409)
                plan = {"id": db.identifier("plan"), "forecast_id": snapshot["id"], "quantities": {p["item"]: p["dinner_total_kg"]},
                        "fresh_quantities": {p["item"]: p["fresh_preparation_kg"]}, "reuse_quantities": {p["item"]: p["quantity_kg"]},
                        "approved_by": request.approved_by, "approved_at": db.now(), "dataset_version": db.version(conn),
                        "assumptions": snapshot["assumptions"], "manual_items": [p["item"]] if snapshot["items"][0]["status"] != "ready" else [],
                        "reuse_id": p["id"], "reuse_state": "approved", "source": p["source"], "decisions": {}}
                db.put(conn, "plans", plan)
                p.update(state="approved", plan_id=plan["id"], label="Approved dinner allocation; record actual use to complete")
            else:
                p.update(state="rejected", label="Rejected; reserved mass released")
                if p.get("plan_id"):
                    plan = require(conn, "plans", p["plan_id"])
                    plan["reuse_state"] = "rejected"
                    db.put(conn, "plans", plan)
            p.update(manager_decision=request.model_dump(), decided_at=db.now())
            db.put(conn, "reuse_plans", p)
            audit(conn, "dinner_reuse_"+p["state"], id, request.model_dump())
            return p

    @router.get("/reuse/plans")
    def reuse_plans():
        with db.connect() as conn:
            return db.all_objects(conn, "reuse_plans")

    @router.get("/biogas/defaults")
    def defaults():
        return {"assumptions": BiogasAssumptions().model_dump(),
                "label": "Editable illustrative assumptions, not measured processor performance",
                "units": "Wet food kg → biogas m³ → methane m³ × methane kWh/m³ → potential kWh",
                "source": "https://www.epa.gov/agstar/how-does-anaerobic-digestion-work"}

    @router.post("/biogas/estimate")
    def estimate(request: BiogasEstimateRequest):
        with db.connect() as conn:
            b = require(conn, "batches", request.batch_id)
            processor = next((p for p in partners if p["id"] == request.partner_id and p["demo"] and "biogas" in p["routes"] and b["origin"] in p["accepts"]), None)
            if not processor:
                raise DomainError("processor_acceptance_required", "Explicit processor acceptance of this material is required.")
            if request.segregation_confirmed is not True:
                raise DomainError("segregation_required", "Record segregation confirmation before estimating this pathway.")
            if request.quantity_kg > batch_view(conn, b)["remaining_kg"] + 1e-9:
                raise DomainError("allocation_exceeded", "Estimate exceeds remaining unreserved batch mass.")
            return {**biogas_potential(request.quantity_kg, request.assumptions.model_dump()), "processor": processor,
                    "outcome": "Preview only; no allocation, handoff, gas or energy recorded"}

    @router.get("/circular/impact")
    def circular_impact():
        with db.connect() as conn:
            reuse = db.all_objects(conn, "reuse_plans")
            actuals = [db.payload(r) for r in conn.execute("SELECT payload FROM records WHERE kind='actual'")]
            gross_service_food = sum(r["prepared_kg"] for r in actuals)
            recorded_reuse = sum(p["quantity_kg"] for p in reuse if p["state"] == "completed")
            receipts = [h for h in db.all_objects(conn, "handoffs") if h["route"] == "biogas" and h.get("simulated", True)]
            for h in receipts:
                h["processor"] = next((p["name"] for p in partners if p["id"] == h["partner_id"]), h["partner_id"])
                h["origin"] = require(conn, "batches", h["batch_id"])["origin"]
                h["outcome"] = "Simulated processor handoff; no energy generation recorded"
            return {"reuse_plans": reuse, "biogas_receipts": receipts,
                    "reserved_reuse_kg": sum(p["quantity_kg"] for p in reuse if p["state"] in {"pending", "approved"}),
                    "staff_recorded_reuse_kg": recorded_reuse,
                    "gross_actual_service_food_kg": gross_service_food,
                    "newly_prepared_actual_food_kg": gross_service_food-recorded_reuse,
                    "simulated_biogas_kg": sum(h["quantity_kg"] for h in receipts),
                    "potential_useful_energy_kwh": sum(h.get("potential", {}).get("useful_energy_kwh", 0) for h in receipts),
                    "potential_covered_kg": sum(h["quantity_kg"] for h in receipts if h.get("potential")),
                    "actual_measured_energy_kwh": None,
                    "caveat": "Reuse is a transfer between meal services, not new food or proven waste prevention. Do not add reused mass to consumed mass. Synthetic records remain synthetic. Biogas figures are theoretical; all processor handoffs are simulated."}

    app.include_router(router)
