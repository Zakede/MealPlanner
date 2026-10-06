import json

from mealplanner import plans, store
from mealplanner.db import execute, query


def recipe_named(name):
    return next(r for r in store.recipes() if r["name"] == name)


def test_garlic_powder_replaces_fresh_garlic(profile, client):
    client.post("/pantry/staples", data={"use_garlic": "Garlic powder", "use_olive_oil": "Cooking spray"})
    with profile.app_context():
        r = recipe_named("Garlic soy chicken thighs & potatoes")
        names = {i["name"]: i for i in r["ingredients"]}
        assert "Garlic" not in names and "Garlic powder" in names
        assert names["Garlic powder"]["grams"] == 8 * 0.2 and names["Garlic powder"]["instead_of"] == "Garlic"
        assert "Cooking spray" in names
        raw = store.recipe(r["id"], raw=True)
        assert "Garlic" in {i["name"] for i in raw["ingredients"]}          # the recipe itself is unchanged
        assert r["per_serving"]["kcal"] < raw["per_serving"]["kcal"]         # spray saves calories


def test_always_have_keeps_staples_off_the_list(profile, client):
    client.post("/pantry/staples", data={"have_soy_sauce": "1", "have_garlic": "1", "use_garlic": "Grated garlic (tube)"})
    client.post("/plan/generate")
    client.post("/plan/approve")
    with profile.app_context():
        first, _ = plans.current_week()
        names = {i["name"] for i in plans.shopping_list(first)}
        assert "Soy sauce" not in names and "Grated garlic (tube)" not in names and "Garlic" not in names


def test_staples_page_and_setup_render(profile, client):
    assert "Garlic powder" in client.get("/pantry/staples").get_data(as_text=True)
    assert "What you use instead" in client.get("/setup/").get_data(as_text=True)
