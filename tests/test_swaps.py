from datetime import date, timedelta

from mealplanner import plans, store, swaps
from mealplanner.db import execute, query
from mealplanner.food_guess import guess, validate_ai

MON = date(2026, 10, 5)


def food_id(name):
    return store.food_by_name(name)["id"]


def chicken_meal():
    return query("""SELECT pm.* FROM plan_meals pm JOIN recipe_ingredients ri ON ri.recipe_id = pm.recipe_id
                    JOIN foods f ON f.id = ri.food_id WHERE f.name = 'Chicken breast' AND pm.kind = 'cook'
                    AND pm.status = 'draft' LIMIT 1""", one=True)


def test_swap_chicken_for_ground_beef_in_one_meal(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        meal = chicken_meal()
        assert meal, "expected a chicken meal in the plan"
        old_recipe = store.recipe(meal["recipe_id"])
        chicken, beef = food_id("Chicken breast"), food_id("Ground beef")
    client.post(f"/cook/{meal['id']}/swap", data={"old_food": chicken, "new_food": beef, "scope": "meal"})
    with profile.app_context():
        after = query("SELECT * FROM plan_meals WHERE id = ?", (meal["id"],), one=True)
        new_recipe = store.recipe(after["recipe_id"])
        assert after["recipe_id"] != meal["recipe_id"]
        names = {i["name"] for i in new_recipe["ingredients"]}
        assert "Ground beef" in names and "Chicken breast" not in names
        assert "chicken" not in new_recipe["name"].lower()
        # protein kept about the same, more fat so more kcal
        assert after["protein"] == __import__("pytest").approx(meal["protein"], rel=0.15)
        assert after["kcal"] > meal["kcal"]
        assert store.recipe(old_recipe["id"])            # the original stays untouched


def test_swap_whole_week_and_use_less(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        meal = chicken_meal()
        chicken, pork = food_id("Chicken breast"), food_id("Ground pork")
    client.post(f"/cook/{meal['id']}/swap", data={"old_food": chicken, "new_food": pork, "scope": "week", "less": "1"})
    with profile.app_context():
        left = query("""SELECT COUNT(*) FROM plan_meals pm JOIN recipe_ingredients ri ON ri.recipe_id = pm.recipe_id
                        WHERE ri.food_id = ? AND pm.status = 'draft' AND pm.kind != 'leftover'""", (chicken,), one=True)[0]
        assert left == 0
        assert query("SELECT score FROM taste_scores WHERE food_id = ?", (chicken,), one=True)["score"] == "small"


def test_grams_keep_protein_within_limits():
    chicken = {"category": "poultry", "protein": 23.3}
    beef = {"category": "meat", "protein": 17.1}
    rice = {"category": "grain", "protein": 2.5}
    assert swaps.swap_grams(150, chicken, beef) == 205
    assert swaps.swap_grams(150, chicken, rice) == 150          # not protein: same weight
    assert swaps.swap_grams(100, {"category": "meat", "protein": 30}, {"category": "soy", "protein": 5}) == 160


def test_renamed_keeps_case():
    assert swaps.renamed("Chicken teriyaki rice bowl", "Chicken breast", "Ground beef") == "Ground beef teriyaki rice bowl"
    assert swaps.renamed("Cut the chicken into pieces.", "Chicken breast", "Ground beef") == "Cut the ground beef into pieces."


def test_food_guess_table_and_ai_check():
    g = guess("Lean ground beef 赤身")
    assert g["category"] == "meat" and g["protein"] == 20.0
    assert guess("合いびき肉")["kcal"] == 236
    assert guess("eggplant")["category"] == "veg"
    assert guess("dragon fruit smoothie xyz") is None
    ok = validate_ai({"kcal": 250, "protein": 17, "carbs": 0, "fat": 20, "price_jpy": 240, "category": "meat"})
    assert ok and ok["price_jpy"] == 240
    assert validate_ai({"kcal": 50, "protein": 30, "carbs": 30, "fat": 30}) is None   # macros don't add up


def test_new_food_without_numbers_gets_estimates(profile, client):
    client.post("/pantry/foods/new", data={"name": "Ground lamb"})
    client.post("/pantry/foods/new", data={"name": "Mystery spice paste"})
    with profile.app_context():
        lamb = store.food_by_name("Ground lamb")
        assert lamb["kcal"] > 0 and lamb["category"] == "meat" and lamb["current_price"]
    r = client.get("/pantry/foods/guess?name=ground%20beef").get_json()
    assert r["category"] == "meat" and r["price_jpy"] == 250


def test_planner_spreads_proteins(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        rows = query("""SELECT pm.recipe_id FROM plan_meals pm WHERE pm.kind IN ('cook', 'nocook')
                        AND pm.slot IN ('lunch', 'dinner')""")
        from mealplanner.planner import main_protein
        cats = [main_protein(store.recipe(r["recipe_id"]))[1] for r in rows]
        assert cats and cats.count("poultry") <= len(cats) * 0.6
