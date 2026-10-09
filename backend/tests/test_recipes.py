import pytest
from backend.app import db, recipes


def review(client, id="INV-1", **changes):
    return client.patch(f"/api/inventory/{id}/review", json={"label_kind": "use_by", "storage_verified": True,
                        "condition_passed": True, "reviewed_by": "Staff", "procedure_reference": "INV-DEMO",
                        "review_date": "2026-10-09", **changes})


def suggestions(client, **query):
    return client.get("/api/recipes/recommendations", params={"as_of": "2026-10-09", **query})


def test_legacy_unknown_labels_fail_closed_without_mutation(client):
    before = client.get("/api/inventory").json()
    r = suggestions(client).json()
    assert r["recipes"] == [] and all(not i["recipe_eligible"] for i in r["inventory"])
    assert client.get("/api/inventory").json() == before


def test_recipe_quantities_raw_units_shortages_and_alternative_plans(client):
    assert review(client).status_code == 200
    r = suggestions(client, portions=200).json()
    rice = next(p for p in r["recipes"] if p["id"] == "tomato-rice")
    tomatoes = next(i for i in rice["ingredients"] if i["ingredient"] == "Tomatoes")
    raw_rice = next(i for i in rice["ingredients"] if i["ingredient"] == "Rice")
    assert tomatoes["required_raw_kg"] == tomatoes["eligible_available_raw_kg"] == tomatoes["planned_usage_raw_kg"] == 12
    assert tomatoes["shortage_raw_kg"] == 0 and tomatoes["batch_allocations"][0]["batch_id"] == "INV-1"
    assert raw_rice["required_raw_kg"] == raw_rice["shortage_raw_kg"] == 16
    assert rice["cooked_output_kg"] is None and rice["near_use_by_usage_raw_kg"] == 12
    assert rice["status"] == "procurement_required"
    assert "not simultaneous" in rice["allocation_note"]
    assert {p["dish"] for p in r["recipes"]} == {"Tomato rice", "Tomato dal"}
    assert "Paneer" in next(p for p in r["excluded_recipes"] if p["dish"] == "Paneer in tomato gravy")["ingredients"]
    assert next(i for i in client.get("/api/inventory").json()["items"] if i["id"] == "INV-1")["quantity_kg"] == 12


@pytest.mark.parametrize("changes", [{"storage_verified": None}, {"storage_verified": False}, {"condition_passed": False},
                                      {"condition_passed": None}, {"label_kind": "unknown"}, {"review_date": "2026-10-08"}])
def test_unsafe_unverified_stale_or_unknown_stock_never_recommended(client, changes):
    review(client, **changes)
    assert suggestions(client).json()["recipes"] == []


def test_useby_and_bestbefore_are_distinct_both_excluded_after_label(client):
    review(client, "INV-3", label_kind="use_by")
    item = next(i for i in suggestions(client).json()["inventory"] if i["id"] == "INV-3")
    assert not item["recipe_eligible"] and item["date_meaning"] == "Safety date"
    assert "Past use-by: blocked" in item["recipe_blockers"]
    review(client, "INV-3", label_kind="best_before")
    item = next(i for i in suggestions(client).json()["inventory"] if i["id"] == "INV-3")
    assert not item["recipe_eligible"] and item["date_meaning"] == "Quality date"
    assert any("quality date" in s for s in item["recipe_blockers"])
    review(client, label_kind="best_before")
    r = suggestions(client).json()
    assert r["recipes"] and all(p["near_use_by_usage_raw_kg"] == 0 for p in r["recipes"])


def test_usage_never_exceeds_stock_multiple_batches_first_date_first(client):
    review(client)
    with db.connect(write=True) as conn:
        item = db.get(conn, "inventory", "INV-1")
        db.put(conn, "inventory", {**item, "id": "INV-4", "quantity_kg": 2, "expiry_date": "2026-10-09"})
    rice = next(r for r in suggestions(client, portions=300).json()["recipes"] if r["id"] == "tomato-rice")
    t = next(i for i in rice["ingredients"] if i["ingredient"] == "Tomatoes")
    assert t["required_raw_kg"] == 18 and t["planned_usage_raw_kg"] == 14 and t["shortage_raw_kg"] == 4
    assert [a["batch_id"] for a in t["batch_allocations"]] == ["INV-4", "INV-1"]
    assert sum(a["use_raw_kg"] for a in t["batch_allocations"]) == t["planned_usage_raw_kg"]


def test_inventory_reviews_persist_audit_and_reset_legacy(client):
    review(client)
    db.bootstrap()
    assert suggestions(client).json()["recipes"]
    assert any(a["action"] == "inventory_eligibility_reviewed" for a in client.get("/api/audit").json())
    client.post("/api/demo/reset", json={"confirm": "RESET SYNTHETIC DEMO"})
    assert suggestions(client).json()["recipes"] == []


def test_inventory_review_inputs_no_blank_staff_or_invalid_portions(client):
    assert review(client, reviewed_by="   ").status_code == 422
    assert suggestions(client, portions=0).status_code == 422
    assert suggestions(client, portions="1.5").status_code == 422
