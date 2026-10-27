"""Inventory endpoints should not silently assess stock against an old demo day."""
from backend.app import db


def test_inventory_and_recipes_default_to_current_kitchen_day(client, monkeypatch):
    # Already the next calendar day in the kitchen, while the UTC host is not.
    monkeypatch.setattr(db, "now", lambda: "2030-01-01T20:00:00+00:00")
    for path in ["/api/inventory", "/api/recipes/recommendations"]:
        result = client.get(path)
        assert result.status_code == 200
        assert result.json()["as_of"] == "2030-01-02"
        assert client.get(path, params={"as_of": "2026-10-09"}).json()["as_of"] == "2026-10-09"
