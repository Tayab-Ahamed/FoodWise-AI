"""Offline raw-ingredient planning. No cooked yield, food safety or nutrition claims."""
from datetime import date
from fastapi import APIRouter, Query
from . import db
from .schemas import InventoryReview

# Illustrative hostel recipe bills for 100 portions, not validated nutrition or cooked yields.
RECIPES = [
    {"id": "tomato-rice", "dish": "Tomato rice", "raw_kg_per_100": {"Tomatoes": 6, "Rice": 8, "Onions": 2, "Oil": .5, "Salt": .15}, "allergens": [],
     "method": "Kitchen-reviewed tomato and onion base with separately cooked rice; verify local recipe, seasoning and cooked yield."},
    {"id": "tomato-dal", "dish": "Tomato dal", "raw_kg_per_100": {"Tomatoes": 4, "Lentils": 5, "Onions": 1, "Oil": .4, "Salt": .15}, "allergens": [],
     "method": "Cook lentils and a tomato base under the kitchen's procedure; verify portions and all ingredient labels."},
    {"id": "paneer-tomato", "dish": "Paneer in tomato gravy", "raw_kg_per_100": {"Tomatoes": 5, "Paneer": 6, "Onions": 2, "Oil": .5, "Salt": .15}, "allergens": ["milk"],
     "method": "Prepare a tomato base and paneer dish under the kitchen procedure; retain milk allergen information."},
    {"id": "spinach-dal", "dish": "Spinach dal", "raw_kg_per_100": {"Spinach": 4, "Lentils": 5, "Tomatoes": 2, "Oil": .4, "Salt": .15}, "allergens": [],
     "method": "Only reviewed, in-date spinach may enter this recipe. Follow the kitchen's preparation procedure."},
]


def eligibility(item, as_of):
    kind = item.get("label_kind", "unknown")
    delta = (date.fromisoformat(item["expiry_date"]) - as_of).days
    reasons = []
    if kind == "unknown":
        reasons.append("Date-label type unknown; staff must distinguish use-by from best-before.")
    if delta < 0:
        reasons.append("Past use-by: blocked" if kind == "use_by" else "Past best-before: quality date, separate kitchen review required; excluded from this planner" if kind == "best_before" else "Past unclassified label date: blocked pending review")
    if item.get("storage_verified") is not True or item.get("condition_passed") is not True:
        reasons.append("Storage and ingredient condition must both be explicitly verified; unknown or failed is blocked.")
    if item.get("review_date") != as_of.isoformat() or not item.get("reviewed_by") or not item.get("procedure_reference"):
        reasons.append("A staff inventory review for the selected planning date is required.")
    if item["quantity_kg"] <= 0:
        reasons.append("No stock available")
    return {"recipe_eligible": not reasons, "recipe_blockers": reasons, "label_kind": kind,
            "days_until_label_date": delta, "date_meaning": "Safety date" if kind == "use_by" else "Quality date" if kind == "best_before" else "Unclassified date"}


def recommendations(items, as_of, portions, near_days):
    stock = [{**i, **eligibility(i, as_of)} for i in items]
    eligible = [i for i in stock if i["recipe_eligible"]]
    near = [i for i in eligible if 0 <= i["days_until_label_date"] <= near_days]
    results, excluded = [], []
    for recipe in RECIPES:
        triggers = [i for i in near if i["ingredient"] in recipe["raw_kg_per_100"]]
        if not triggers:
            continue
        blocked = [name for name in recipe["raw_kg_per_100"] if any(i["ingredient"] == name for i in stock)
                   and not any(i["ingredient"] == name for i in eligible)]
        if blocked:
            excluded.append({"dish": recipe["dish"], "reason": "Existing ingredient stock is ineligible; no suggestion to use it.", "ingredients": blocked})
            continue
        ingredients, use_by_usage, total_usage, total_shortage = [], 0, 0, 0
        for name, per_100 in recipe["raw_kg_per_100"].items():
            required = per_100 * portions / 100
            candidates = sorted([i for i in eligible if i["ingredient"] == name], key=lambda i: (i["expiry_date"], i["id"]))
            available = sum(i["quantity_kg"] for i in candidates)
            left, allocations = required, []
            for i in candidates:
                use = min(left, i["quantity_kg"])
                if use > 0:
                    allocations.append({"batch_id": i["id"], "use_raw_kg": use, "label_kind": i["label_kind"], "label_date": i["expiry_date"], "source": i.get("source", "unknown")})
                    total_usage += use
                    if i["label_kind"] == "use_by" and i["days_until_label_date"] <= near_days:
                        use_by_usage += use
                    left -= use
            shortage = max(0, required-available)
            total_shortage += shortage
            ingredients.append({"ingredient": name, "required_raw_kg": required, "eligible_available_raw_kg": available,
                                "planned_usage_raw_kg": min(required, available), "shortage_raw_kg": shortage, "batch_allocations": allocations})
        results.append({**recipe, "portions": portions, "ingredients": ingredients, "near_use_by_usage_raw_kg": use_by_usage,
                        "planned_inventory_usage_raw_kg": total_usage, "shortage_raw_kg": total_shortage,
                        "status": "procurement_required" if total_shortage > 1e-9 else "inventory_available",
                        "cooked_output_kg": None, "label": "Planning suggestion; kitchen review and full ingredient/allergen checks required",
                        "allocation_note": "Alternative scenarios, not simultaneous reservations. Inventory is not consumed or reserved by viewing a recipe."})
    results.sort(key=lambda r: (-r["near_use_by_usage_raw_kg"], r["shortage_raw_kg"], r["id"]))
    return {"as_of": str(as_of), "portions": portions, "near_days": near_days, "inventory": stock, "recipes": results,
            "excluded_recipes": excluded, "units": "Raw ingredient kg only; cooked yield unknown. Not a cooked-food forecast.",
            "caveat": "Illustrative bills of ingredients for planning, not nutritionally validated meals. Missing ingredients require verified procurement. Expired use-by, past best-before, unsafe or unknown stock is excluded; best-before is a quality date, not a use-by safety deadline."}


def register(app, require, audit):
    router = APIRouter(prefix="/api", tags=["Offline ingredient planning"])

    @router.patch("/inventory/{id}/review")
    def review_inventory(id: str, request: InventoryReview):
        with db.connect(write=True) as conn:
            item = require(conn, "inventory", id)
            item.update(request.model_dump(mode="json"), inventory_reviewed_at=db.now())
            db.put(conn, "inventory", item)
            audit(conn, "inventory_eligibility_reviewed", id, request.model_dump(mode="json"))
            return {**item, **eligibility(item, request.review_date)}

    @router.get("/recipes/recommendations")
    def suggest(as_of: date = date(2026, 10, 9), portions: int = Query(default=100, ge=1, le=100000), near_days: int = Query(default=2, ge=0, le=30)):
        with db.connect() as conn:
            return recommendations(db.all_objects(conn, "inventory"), as_of, portions, near_days)

    app.include_router(router)
