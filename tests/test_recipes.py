import pytest

from mealplanner import store
from mealplanner.db import query


def buldak(app):
    with app.app_context():
        rid = query("SELECT id FROM recipes WHERE name LIKE 'Buldak noodles%'", one=True)["id"]
        return store.recipe(rid)


def test_seeded_recipes_have_computed_macros(app):
    r = buldak(app)
    s = r["per_serving"]
    # 140 g ramen + 60 g onion + 35 g pepper + 40 g lettuce
    expected = 140 * 3.79 + 60 * 0.37 + 35 * 0.22 + 40 * 0.12
    assert s["kcal"] == pytest.approx(expected)
    assert s["cost"] == pytest.approx(140 * 1.8 + 60 * 0.4 + 35 * 1.0 + 40 * 0.8)
    assert "wheat" in r["allergens"]


def test_batch_recipe_divides_by_servings(app):
    with app.app_context():
        rid = query("SELECT id FROM recipes WHERE batch_ok = 1 AND servings = 4", one=True)["id"]
        r = store.recipe(rid)
        total = sum(i["grams"] * i["kcal"] / 100 for i in r["ingredients"])
        assert r["per_serving"]["kcal"] == pytest.approx(total / 4)


def test_cost_follows_latest_pantry_price(app, client):
    before = buldak(app)["per_serving"]["cost"]
    client.post("/pantry/new", data={
        "name": "Buldak ramen", "quantity": "5", "unit": "pcs", "price_paid": "700",
        "location": "shelf", "kcal": "379", "protein": "8.6", "carbs": "59.3", "fat": "12.1",
    })
    after = buldak(app)["per_serving"]["cost"]
    # 700 yen / 700 g = 100 yen per 100 g, down from the 180 reference price
    assert after == pytest.approx(before - 140 * 0.8)


def form(**kw):
    data = {"name": "Tuna rice", "active_min": "5", "total_min": "5", "servings": "1", "spice_level": "0",
            "thaw_hours": "0", "fridge_days": "2", "tags": "Quick, Savory", "cuisine": "Japanese",
            "type_lunch": "on", "steps": "Mix.\nEat.",
            "ing_name": ["Canned tuna", "Cooked rice", ""], "ing_grams": ["70", "150", ""]}
    data.update(kw)
    return data


def test_create_recipe(app, client):
    resp = client.post("/recipes/new", data=form(), follow_redirects=True)
    assert b"Tuna rice" in resp.data
    with app.app_context():
        r = store.recipe(query("SELECT id FROM recipes WHERE name = 'Tuna rice'", one=True)["id"])
        assert r["tags"] == "quick,savory"
        assert r["meal_types"] == "lunch"
        assert r["per_serving"]["protein"] == pytest.approx(0.7 * 16 + 1.5 * 2.5)


def test_unknown_food_rejected(app, client):
    resp = client.post("/recipes/new", data=form(ing_name=["Dragonfruit"], ing_grams=["100"]), follow_redirects=True)
    assert b"unknown food" in resp.data


def test_edit_replaces_ingredients(app, client):
    client.post("/recipes/new", data=form())
    with app.app_context():
        rid = query("SELECT id FROM recipes WHERE name = 'Tuna rice'", one=True)["id"]
    client.post(f"/recipes/{rid}/edit", data=form(ing_name=["Canned tuna"], ing_grams=["140"]))
    with app.app_context():
        assert len(store.recipe(rid)["ingredients"]) == 1


def test_scaled_view(client):
    resp = client.get("/recipes/1?portions=2")
    assert resp.status_code == 200 and b"2 portions" in resp.data


def test_pages_render(client):
    for url in ("/recipes/", "/recipes/?type=snack", "/recipes/new", "/recipes/1/edit", "/recipes/boosters", "/recipes/api"):
        assert client.get(url).status_code == 200
