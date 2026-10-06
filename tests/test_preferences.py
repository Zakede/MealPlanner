import json
import sqlite3
from datetime import date, timedelta

import pytest

from mealplanner import create_app, plans, store
from mealplanner.db import execute, query
from mealplanner.diet import allowed
from mealplanner.nutrition import activity_multiplier
from mealplanner.recipe_ai import recipe_from_jsonld

MON = date(2026, 10, 5)
WED = date(2026, 10, 7)
SUN = MON + timedelta(days=6)


def test_activity_multiplier_separates_job_and_training():
    assert activity_multiplier("desk", 0, "moderate") == 1.2
    assert activity_multiplier("physical", 0, "moderate") == 1.5
    assert activity_multiplier("desk", 4, "hard") == pytest.approx(1.4)
    assert activity_multiplier("physical", 7, "hard") == pytest.approx(1.85)
    assert activity_multiplier("nonsense", 99, "nonsense") <= 2.0


def recipe_named(app, name):
    with app.app_context():
        return store.recipe(query("SELECT id FROM recipes WHERE name = ?", (name,), one=True)["id"])


def test_diet_filters(app):
    chicken = recipe_named(app, "Chicken teriyaki rice bowl")
    tofu = recipe_named(app, "Tofu scramble")
    salmon = recipe_named(app, "Easy salmon teriyaki")
    eggs = recipe_named(app, "Egg & cheese toast")
    keto = recipe_named(app, "Keto chicken thighs with avocado salad")
    assert allowed(chicken, "any", []) and not allowed(chicken, "vegetarian", [])
    assert allowed(tofu, "vegan", [])
    assert allowed(salmon, "pescatarian", []) and not allowed(salmon, "vegetarian", [])
    assert allowed(eggs, "vegetarian", []) and not allowed(eggs, "vegan", [])
    assert allowed(keto, "keto", []) and not allowed(chicken, "keto", [])
    assert not allowed(salmon, "any", ["fish"])
    assert not allowed(recipe_named(app, "Ginger pork with cabbage"), "any", ["pork"])


def test_vegan_week_has_no_animal_products(profile):
    with profile.app_context():
        execute("UPDATE settings SET diet = 'vegan' WHERE id = 1")
        plans.generate_week(MON)
        for m in plans.meals_between(MON, SUN):
            if m["recipe"]:
                cats = {i["category"] for i in m["recipe"]["ingredients"]}
                assert not cats & {"poultry", "meat", "fish", "seafood", "egg", "dairy"}, m["title"]


def test_no_fish_toggle(profile):
    with profile.app_context():
        execute("UPDATE settings SET avoid = 'fish,seafood' WHERE id = 1")
        plans.generate_week(MON)
        for m in plans.meals_between(MON, SUN):
            if m["recipe"]:
                assert not {i["category"] for i in m["recipe"]["ingredients"]} & {"fish", "seafood"}


def test_never_again_swaps_out_of_plan(profile, client):
    with profile.app_context():
        plans.generate_week(MON)
        meal = next(m for m in plans.meals_between(WED, SUN) if m["kind"] in ("cook", "nocook") and m["slot"] == "dinner")
    resp = client.post(f"/recipes/{meal['recipe_id']}/pref", data={"status": "never"}, follow_redirects=True)
    assert b"Won&#39;t plan this again" in resp.data or b"Won't plan this again" in resp.data
    with profile.app_context():
        assert store.recipe_prefs()[meal["recipe_id"]] == "never"
        left = [m for m in plans.meals_between(WED, SUN) if m["recipe_id"] == meal["recipe_id"]
                and m["status"] in plans.EDITABLE]
        assert not left
        plans.generate_week(MON)
        assert not [m for m in plans.meals_between(WED, SUN) if m["recipe_id"] == meal["recipe_id"]]


def test_favorites_show_up_more(profile):
    with profile.app_context():
        fav = query("SELECT id FROM recipes WHERE name = 'Miso eggplant & chicken'", one=True)["id"]
        plans.generate_week(MON)
        before = sum(1 for m in plans.meals_between(WED, SUN) if m["recipe_id"] == fav)
        store.set_recipe_pref(fav, "favorite")
        plans.generate_week(MON)
        after = sum(1 for m in plans.meals_between(WED, SUN) if m["recipe_id"] == fav)
        assert after >= max(1, before)


def test_add_meal_sizes_portion(profile, client):
    with profile.app_context():
        rid = query("SELECT id FROM recipes WHERE name = 'Oyakodon'", one=True)["id"]
    client.post("/plan/add", data={"date": "2026-10-08", "slot": "dinner", "recipe_id": rid})
    with profile.app_context():
        m = next(m for m in plans.meals_between(date(2026, 10, 8), date(2026, 10, 8)) if m["recipe_id"] == rid)
        assert m["note"] == "Added by you" and 400 < m["kcal"] < 1100
    assert client.get("/plan/add?date=2026-10-08&slot=lunch").status_code == 200


def wizard_form(**kw):
    data = {"sex": "male", "age": "30", "height_cm": "180", "weight_kg": "90", "goal_weight_kg": "80",
            "pace_kg_week": "0.5", "job": "standing", "training_days": "4", "training_intensity": "hard",
            "work_0": "on", "work_1": "on", "work_2": "on", "work_3": "on", "work_4": "on",
            "work_start": "09:00", "work_end": "18:00", "commute_min": "30", "gym_1": "on", "gym_3": "on",
            "weekday_effort": "low", "weekend_effort": "full", "diet": "vegetarian", "avoid_spicy": "on",
            "allergies": "peanut", "dislikes": "", "spice_tolerance": "2", "flavor_garlicky": "on",
            "cuisine_italian": "on", "weekly_budget_yen": "9000", "eat_out_slots": "1", "eat_out_budget_yen": "1000"}
    data.update(kw)
    return data


def test_setup_wizard_saves_everything_and_plans(app, client):
    assert client.get("/setup/").status_code == 200
    resp = client.post("/setup/", data=wizard_form())
    assert resp.status_code == 302 and "/plan/" in resp.headers["Location"]
    with app.app_context():
        s = store.settings()
        assert s["setup_done"] == 1 and s["diet"] == "vegetarian" and s["job"] == "standing"
        assert s["avoid"] == "spicy" and s["flavor_likes"] == "garlicky"
        sched = {r["weekday"]: dict(r) for r in query("SELECT * FROM schedule_days")}
        assert sched[5]["work_start"] is None and sched[5]["effort"] == "full"
        assert sched[1]["gym"] == 1 and sched[0]["gym"] == 0
        assert plans.meals_between(WED, SUN)
    assert client.get("/").status_code == 200


def test_setup_wizard_rejects_missing_sex(client):
    resp = client.post("/setup/", data=wizard_form(sex=""), follow_redirects=True)
    assert b"pick male or female" in resp.data.lower()


def test_jsonld_recipe_extraction():
    page = """<html><script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
      {"@type": "WebPage"}, {"@type": "Recipe", "name": "Garlic chicken", "recipeYield": "2",
       "recipeIngredient": ["300 g chicken", "2 cloves garlic"],
       "recipeInstructions": [{"@type": "HowToStep", "text": "Fry it."}]}]}</script></html>"""
    text = recipe_from_jsonld(page)
    assert "Garlic chicken" in text and "300 g chicken" in text and "Fry it." in text
    assert recipe_from_jsonld("<html>nothing</html>") is None


def test_import_from_text(app, client):
    class Fake:
        model = "fake"

        def complete(self, prompt):
            assert "garlic butter chicken" in prompt
            return json.dumps({"name": "Garlic chicken", "servings": 1, "ingredients": [
                {"food": "Chicken breast", "grams": 150}, {"food": "Garlic", "grams": 6}],
                "steps": ["Fry until cooked through."], "meal_types": ["dinner"]})
    app.config["LLM_PROVIDER"] = Fake()
    resp = client.post("/recipes/import", data={"source": "garlic butter chicken: 1 chicken breast..."})
    assert resp.status_code == 200 and b"Garlic chicken" in resp.data and b"Another idea" not in resp.data


def test_old_database_upgrades(tmp_path):
    """A database from before the library rework loses the retired recipes and gains the new ones."""
    path = tmp_path / "old.db"
    app = create_app({"DATABASE": str(path), "TODAY": "2026-10-07"})
    conn = sqlite3.connect(path)
    food = conn.execute("SELECT id FROM foods LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO recipes (name) VALUES ('Buldak chicken & cabbage bowl')")
    rid = conn.execute("SELECT id FROM recipes WHERE name = 'Buldak chicken & cabbage bowl'").fetchone()[0]
    conn.execute("INSERT INTO recipe_ingredients (recipe_id, food_id, grams) VALUES (?, ?, 100)", (rid, food))
    conn.execute("DELETE FROM recipes WHERE name = 'Mapo tofu'")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    app = create_app({"DATABASE": str(path), "TODAY": "2026-10-07"})
    with app.app_context():
        names = {r["name"] for r in query("SELECT name FROM recipes")}
        assert "Buldak chicken & cabbage bowl" not in names and "Mapo tofu" in names
