import pytest

from mealplanner import store
from mealplanner.db import query


def teriyaki(app):
    with app.app_context():
        rid = query("SELECT id FROM recipes WHERE name = 'Chicken teriyaki rice bowl'", one=True)["id"]
        return store.recipe(rid)


def test_seeded_recipes_have_computed_macros(app):
    r = teriyaki(app)
    s = r["per_serving"]
    # 150 g chicken, 180 g rice, 15 g soy sauce, 15 g mirin, 80 g broccoli
    expected = 150 * 1.05 + 180 * 1.56 + 15 * 0.76 + 15 * 2.41 + 80 * 0.37
    assert s["kcal"] == pytest.approx(expected)
    assert s["cost"] == pytest.approx(150 * 0.85 + 180 * 0.3 + 15 * 0.5 + 15 * 0.6 + 80 * 0.7)
    assert "wheat" in r["allergens"] and "soy" in r["allergens"]


def test_batch_recipe_divides_by_servings(app):
    with app.app_context():
        rid = query("SELECT id FROM recipes WHERE batch_ok = 1 AND servings = 4", one=True)["id"]
        r = store.recipe(rid)
        total = sum(i["grams"] * i["kcal"] / 100 for i in r["ingredients"])
        assert r["per_serving"]["kcal"] == pytest.approx(total / 4)


def test_cost_follows_latest_pantry_price(app, client):
    before = teriyaki(app)["per_serving"]["cost"]
    client.post("/pantry/new", data={
        "name": "Chicken breast", "quantity": "500", "unit": "g", "price_paid": "300",
        "location": "fridge", "kcal": "105", "protein": "23.3", "carbs": "0", "fat": "1.9",
    })
    after = teriyaki(app)["per_serving"]["cost"]
    # 300 yen / 500 g = 60 yen per 100 g vs the 85 reference: chicken gets much cheaper,
    # and the other ingredients drift down a little with your overall price level
    assert before - 150 * 0.25 < after < before - 150 * 0.15


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
