"""Read-only, source-labeled advisor evidence. No model creates facts or numbers."""
import re
from datetime import date, datetime, timedelta, timezone

from . import db, domain, recipes, recipients
from .errors import DomainError

KITCHEN_TZ = timezone(timedelta(hours=5, minutes=30))
TOPICS = {
    "forecast": ("prepare", "preparation", "forecast", "tomorrow", "cook", "demand", "how much", "quantity"),
    "attendance": ("student", "attendance", "diners", "how many", "pulse", "preferences", "intentions"),
    "inventory": ("ingredient", "inventory", "expiry", "expire", "expired", "stock", "use first", "nearing", "use-by"),
    "waste": ("waste", "wasting", "increasing", "trend", "reduce", "leftover"),
    "recovery": ("surplus", "untouched", "redistribut", "donat", "safe", "approve", "handoff", "acceptance", "accepted", "left on plates"),
    "directory": ("ngo", "nearby", "map", "recipient", "receive", "food bank", "charit"),
    "processing": ("biogas", "compost", "energy", "electricity", "processing"),
}
SUGGESTIONS = [
    "How much food should we prepare tomorrow?",
    "Which ingredients are nearing expiry?",
    "Why is our food waste increasing?",
    "What can we do with untouched surplus?",
    "Which nearby NGOs are shown on our map?",
    "How can we reduce plate waste?",
]


def today():
    return datetime.now(KITCHEN_TZ).date()


def resolve(question, history, requested_date, requested_meal, known_items):
    text = question.casefold()
    topics = [topic for topic, words in TOPICS.items() if any(word in text for word in words)]
    # A short follow-up may inherit the prior topic, but never prior factual claims.
    if not topics and history and re.search(r"\b(what about|and|also|that|it|those|dinner|lunch|breakfast)\b", text):
        previous = history[-1].casefold()
        topics = [topic for topic, words in TOPICS.items() if any(word in previous for word in words)]
    mentioned = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    try:
        question_date = date.fromisoformat(mentioned[0]) if mentioned else today() + timedelta(days=1) if "tomorrow" in text else today() if "today" in text else None
    except ValueError:
        raise DomainError("invalid_date", "Use a valid calendar date in YYYY-MM-DD format.")
    question_meal = next((meal for meal in ["breakfast", "lunch", "dinner"] if meal in text), None)
    if requested_date and question_date and requested_date != question_date:
        raise DomainError("conflicting_context", "The question date and selected planning date disagree. Clear or correct the planning context.")
    if requested_meal and question_meal and requested_meal != question_meal:
        raise DomainError("conflicting_context", "The question meal and selected meal disagree. Clear or correct the planning context.")
    items = [item for item in known_items if re.search(r"\b" + re.escape(item.casefold()) + r"\b", text)]
    if not items and history and not any(word in text for words in TOPICS.values() for word in words):
        items = [item for item in known_items if item.casefold() in history[-1].casefold()]
    return topics, question_date or requested_date or today() + timedelta(days=1), question_meal or requested_meal, items


def collect(request):
    with db.connect() as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")  # All evidence and the version come from one SQLite read snapshot.
        version = db.version(conn)
        rows = db.records(conn)
        forecasts = db.all_objects(conn, "forecasts")
        inventory = db.all_objects(conn, "inventory")
        handoffs = db.all_objects(conn, "handoffs")
        snapshots = db.all_objects(conn, "directory_snapshots")
        batches = db.all_objects(conn, "batches")
        acceptances = db.all_objects(conn, "acceptances")
    topics, target_date, meal, items = resolve(request.question, request.history, request.planning_date,
                                             request.meal, sorted({r["item"] for r in rows}))
    cards = []
    record_ids = {r["record_id"] for r in rows}

    def card(id, title, text, path, basis, refs=(), sources=(), metrics=None, source_url=None):
        cards.append({"id": id, "title": title, "text": text, "path": path, "basis": basis,
                      "reference_ids": list(refs)[:200], "reference_count": len(refs),
                      "record_reference_ids": [id for id in refs if id in record_ids][:200],
                      "sources": sorted(set(sources)), "metrics": metrics or {}, "source_url": source_url,
                      "dataset_version": version})

    if "forecast" in topics or "attendance" in topics:
        matched = [f for f in forecasts if f["assumptions"]["date"] == str(target_date)
                   and (not meal or f["assumptions"]["meal"] == meal)
                   and (not items or any(i["item"] in items for i in f["items"]))]
        current = [f for f in matched if f["dataset_version"] == version]
        selected = {}
        for f in sorted(current, key=lambda f: f["created_at"]):
            for i in f["items"]:
                if not items or i["item"] in items:
                    selected[(f["assumptions"]["meal"], i["item"])] = (f, i)
        if not selected:
            reason = "Matching saved forecasts are stale after a data change." if matched else "No matching saved forecast exists."
            card("forecast_missing", "A forecast is needed", f"For {target_date} {meal or 'all meals'}, {reason} Open Plan next meal, enter expected attendance and calculate a forecast. I cannot infer attendance or invent a preparation quantity.",
                 "plan", "Saved forecast snapshots checked against the current dataset version")
        missing_items = [item for item in items if not any(key[1] == item for key in selected)]
        if selected and missing_items:
            card("forecast_partial_missing", "Some item forecasts are missing", "No current matching saved forecast is available for: " + ", ".join(missing_items) + ". Calculate these items in Plan next meal; no quantity is inferred.", "plan", "Current saved item and meal snapshots")
        if len(selected) > 30:
            card("forecast_limit", "Narrow this forecast question", "This answer shows the first thirty item and meal forecasts. Specify an item or meal to narrow the results. These snapshots are separate scenarios; do not add their quantities across different attendance assumptions.", "plan", "Forecast answer size limit")
        for f, i in list(selected.values())[:30]:
            assumption = f["assumptions"]
            refs = [f["id"], *i["history_ids"]]
            basis = f"Saved {assumption['date']} {assumption['meal']} forecast; expected attendance is a planning input, not confirmed attendance"
            if i["status"] != "ready":
                card("forecast_" + f["id"] + "_" + i["item"], i["item"] + ": insufficient history", i["fallback_reason"], "plan", basis, refs, i["data_quality"]["sources"])
                continue
            text = (f"{i['item']}, {assumption['date']} {assumption['meal']}: saved preparation recommendation {i['recommended_kg']:.2f} kg cooked food for {assumption['expected_attendance']} expected diners, including a {assumption['buffer_pct']:g}% buffer. "
                    f"Predicted served demand is {i['demand_kg']:.2f} kg, including plate waste. The historical 10th–90th percentile is {i['range_low_kg']:.2f}–{i['range_high_kg']:.2f} kg; it is not a calibrated confidence interval. "
                    f"The model uses {i['sample_count']} earlier records. This is a suggestion requiring manager review, not an approved plan.")
            if i["data_quality"]["confirmed_shortage_ids"]:
                text += " Confirmed historical shortages may censor demand; review unmet demand before deciding."
            card("forecast_" + f["id"] + "_" + i["item"], i["item"] + ": saved forecast", text, "plan", basis, refs, i["data_quality"]["sources"],
                 {k: i[k] for k in ["recommended_kg", "demand_kg", "range_low_kg", "range_high_kg", "sample_count"]})
        card("served_basis", "What the model predicts", "Served demand equals consumed food plus plate waste. Raw ingredient stock is not cooked-food output. Review both surplus and shortage in the preparation simulator before approving a plan.", "plan", "Existing forecasting and mass-balance rules")
    if "attendance" in topics:
        card("pulse_missing", "Student intentions are unavailable", "Student Meal Pulse is not implemented in this repository, so no student intentions or confirmed future attendance are available. Forecast expected attendance is a manager-entered planning assumption. Past logged attendance describes past services only.", "plan", "Existing application schema and forecast assumptions")
    if "inventory" in topics:
        as_of = target_date if request.planning_date or "tomorrow" in request.question.casefold() or re.search(r"\d{4}-\d{2}-\d{2}", request.question) else today()
        if not inventory:
            card("inventory_empty", "No inventory records", "No inventory batches are recorded. Add stock and document label, storage and condition review before asking what to use first.", "overview", "Current inventory table")
        for stock in sorted(inventory, key=lambda i: (i["expiry_date"], i["id"]))[:30]:
            checked = recipes.eligibility(stock, as_of)
            status = "Eligible for kitchen planning after the documented review; prioritize by label date." if checked["recipe_eligible"] else "Do not use this batch in a recipe yet. " + " ".join(reason.rstrip(".") + "." for reason in checked["recipe_blockers"])
            card("inventory_" + stock["id"], stock["ingredient"] + (": review passed" if checked["recipe_eligible"] else ": held from use"),
                 f"{stock['ingredient']}: {stock['quantity_kg']:.2f} kg raw ingredient stock; {checked['label_kind'].replace('_', '-')} label date {stock['expiry_date']}, assessed for {as_of}. {status} Raw kg must not be treated as cooked kg.",
                 "overview", "Existing inventory eligibility rules, assessed for " + str(as_of), [stock["id"]], [stock.get("source", "unknown")],
                 {"raw_quantity_kg": stock["quantity_kg"], "recipe_eligible": checked["recipe_eligible"], "days_until_label_date": checked["days_until_label_date"]})
        if len(inventory) > 30:
            card("inventory_limit", "More inventory is available", "This answer shows the earliest thirty label dates. Open the inventory panel to review all batches.", "overview", "Inventory answer size limit")
    if "waste" in topics:
        filtered = [r for r in rows if not items or r["item"] in items]
        summary = domain.overview(filtered)
        totals = summary["totals"]
        card("waste_totals", "Recorded waste, separated", f"Across {summary['record_count']} recorded item rows from {summary['date_from'] or 'no start date'} to {summary['date_to'] or 'no end date'}, untouched surplus totals {totals['untouched_surplus_kg']:.2f} kg and plate waste totals {totals['plate_waste_kg']:.2f} kg. These are recorded accounting totals, not demonstrated prevention or savings.", "overview", "Existing overview calculation" + ("; items: " + ", ".join(items) if items else "; all items"), [r["record_id"] for r in filtered], summary["sources"], totals)
        # Compare complete consecutive seven-day windows, anchored to the latest record.
        if filtered:
            end = max(date.fromisoformat(r["date"]) for r in filtered)
            recent = [r for r in filtered if end - timedelta(days=6) <= date.fromisoformat(r["date"]) <= end]
            prior = [r for r in filtered if end - timedelta(days=13) <= date.fromisoformat(r["date"]) < end - timedelta(days=6)]
            def rates(group):
                denominator = sum(r["prepared_kg"] for r in group)
                return sum(r["untouched_surplus_kg"] + r["plate_waste_kg"] for r in group) / denominator * 100 if denominator else None
            a, b = rates(recent), rates(prior)
            if a is not None and b is not None:
                direction = "higher" if a > b else "lower" if a < b else "unchanged"
                card("waste_trend", "Is waste actually increasing?", f"Recorded waste as a share of prepared mass is {a:.2f}% for {end-timedelta(days=6)}–{end}, versus {b:.2f}% for {end-timedelta(days=13)}–{end-timedelta(days=7)}: {direction}. This uses available records, not necessarily complete service coverage. Menu, source and attendance differences can affect the comparison; it does not prove a cause.", "overview", "Two consecutive seven-day windows ending at the latest logged date", [r["record_id"] for r in prior + recent], [r["source"] for r in prior + recent], {"recent_waste_pct": a, "prior_waste_pct": b})
        for finding in domain.investigations(filtered)[:4]:
            metrics = finding["observed_metrics"]
            if "plate_waste_per_diner_kg" in metrics:
                text = f"{finding['title']}: mean plate waste {metrics['plate_waste_per_diner_kg']*1000:.1f} g per diner across {finding['sample_count']} item rows. "
            else:
                text = f"{finding['title']}: Friday untouched surplus {metrics['friday_untouched_per_diner_kg']*1000:.1f} g per diner, compared with {metrics['other_untouched_per_diner_kg']*1000:.1f} g on other weekdays. "
            card("finding_" + finding["id"], finding["title"], text + finding["caveats"] + " " + finding["suggested_action"], "overview", "Existing evidence-backed waste investigation", finding["evidence_record_ids"], summary["sources"], metrics)
        card("portion_trial", "Reduce plate waste through measurement", "Try smaller first portions with optional seconds under manager supervision; compare separately weighed plate waste per diner and record shortages. Lower cooking quantities alone do not establish plate-waste prevention. Any improvement remains unproven until measured.", "impact", "Existing portion-trial measurement protocol")
    if any(topic in topics for topic in ["recovery", "directory", "processing"]) or "plate" in request.question.casefold():
        card("plate_block", "Plate waste: no human redistribution", "Plate waste is always blocked from human redistribution by the backend, regardless of AI output or manager intent. Keep it separate. Non-human processing requires documented segregation and a processor that accepts this material; a map listing is not acceptance.", "recovery", "Authoritative backend review and handoff rules")
        card("untouched_review", "Untouched surplus still needs review", "Untouched origin alone does not establish safety. Document all handling and storage checks, obtain manager approval and confirm recipient acceptance for the specific batch before redistribution. This is policy review, not food-safety certification. The advisor cannot approve or execute any action.", "recovery", "Existing recovery review, approval and dispatch gates")
    if "recovery" in topics:
        card("recovery_records", "Review the batch ledger", f"The recovery ledger contains {len(batches)} recorded batches. Open Recovery to inspect current checks, quantities and manager decisions for a specific batch. Eligibility is assessed by the existing backend workflow; it cannot be conferred by this chat.", "recovery", "Current recovery batch ledger", [b["id"] for b in batches])
    if "recovery" in topics or "directory" in topics:
        current_acceptances = []
        by_batch = {b["id"]: b for b in batches}
        for acceptance in acceptances:
            batch = by_batch.get(acceptance["batch_id"])
            expiry = datetime.fromisoformat(acceptance["expires_at"])
            remaining = acceptance["quantity_kg"] - sum(h["quantity_kg"] for h in handoffs if h.get("acceptance_id") == acceptance["id"])
            if batch and expiry.tzinfo and expiry > datetime.now(timezone.utc) and remaining > 1e-9 and acceptance["origin"] == batch["origin"] and acceptance["batch_quantity_kg"] == batch["quantity_kg"]:
                current_acceptances.append(acceptance)
        card("acceptance_records", "Recorded acceptance is batch-specific", f"There are {len(current_acceptances)} unexpired, unchanged-batch staff-recorded acceptance declarations with remaining accepted capacity, out of {len(acceptances)} saved declarations. These are staff attestations, not independent verification or approval to dispatch. Open Recovery to inspect the recipient, batch, expiry and receipt evidence. The advisor does not infer acceptance from a nearby map pin or authorize a handoff.", "recovery", "Existing acceptance expiry, batch identity and remaining-capacity checks", [a["id"] for a in current_acceptances], metrics={"current_acceptance_count": len(current_acceptances), "saved_acceptance_count": len(acceptances)})
    if "directory" in topics:
        key = ":".join(map(str, (round(request.latitude, 5), round(request.longitude, 5), request.radius_km)))
        snapshot = next((s for s in snapshots if s["id"] == key), None)
        places = sorted(snapshot["places"], key=lambda p: (p["distance_km"], p["name"])) if snapshot else []
        card("directory_scope", "The map provides candidates", f"The map's saved directory contains {len(places)} candidate organizations within the selected {request.radius_km} km radius. " + (f"Last retrieved {snapshot['fetched_at']}. This is a cached listing, not current availability. " if snapshot else "No saved discovery exists for this location; open Field station and request discovery. ") + "Directory entries are not verified food recipients or confirmed acceptance. Distances are straight-line, not travel time.", "station", "Same SQLite directory snapshot used by the existing NGO map", [snapshot["id"]] if snapshot else [], ["OpenStreetMap contributors"] if snapshot else [])
        for place in places[:3]:
            card("place_" + place["id"], place["name"], f"{place['name']} is a community-mapped {place['category'].replace('_', ' ')} candidate, {place['distance_km']:.2f} km in a straight line from the selected location. " + (f"Published address: {place['address']}. " if place["address"] else "No published street address is available. ") + "The listing does not establish food acceptance or collection availability. Check the source and contact the organization before considering a batch.", "station", "Cached map directory entry; no acceptance inferred", [place["id"]], [place["source"]], {"distance_km": place["distance_km"]}, recipients.safe_url(place["source_url"]))
        if recipients.distance_km(request.latitude, request.longitude, 13.086027, 77.641252) < 50:
            contact = recipients.CONTACTS[0]
            card("public_contact", contact["name"] + ": published contact", f"{contact['name']}: {contact['address']}. Published phone {contact['phone']}. Exact coordinates, distance and cooked-food acceptance are not confirmed. This is the same published contact shown in Field station; it is not a partner or accepted handoff.", "station", contact["source"], [contact["id"]], ["Organization website"], source_url=contact["source_url"])
    if "processing" in topics:
        simulated = [h for h in handoffs if h.get("simulated", True) is True]
        measured = [h for h in handoffs if h.get("simulated") is False]
        card("processing_records", "Processing records are not energy measurements", f"The ledger has {len(simulated)} simulated and {len(measured)} non-simulated handoff records across all routes. Inspect each receipt in Impact & evidence; handoff quantities do not establish actual biogas or electricity generation. Supported compost or biogas routes require the existing material-acceptance and segregation checks. Energy estimates are theoretical, based on explicit assumptions; actual energy is not measured by this application.", "impact", "Existing handoff ledger and biogas assumptions", [h["id"] for h in handoffs])
    if not topics:
        card("unsupported", "Choose a kitchen question", "I could not reliably match this question to the available kitchen evidence. Ask about saved forecasts, attendance assumptions, ingredient expiry, recorded waste, recovery or the NGO directory. I cannot change records, approve food or certify safety. No action has been performed.", "overview", "Read-only advisor scope")
    return cards, version, {"topics": topics, "planning_date": str(target_date), "meal": meal, "items": items,
                             "timezone": "Asia/Kolkata", "inventory_as_of": str(as_of) if "inventory" in topics else None}
