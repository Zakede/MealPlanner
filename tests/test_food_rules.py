from datetime import date

from mealplanner import food_rules, plans, store
from mealplanner.db import execute, query


def chicken_meals():
    return query("""SELECT DISTINCT pm.id, r.name, r.steps FROM plan_meals pm JOIN recipes r ON r.id = pm.recipe_id
                    JOIN recipe_ingredients ri ON ri.recipe_id = r.id JOIN foods f ON f.id = ri.food_id
                    WHERE f.category = 'poultry' AND pm.status IN ('draft', 'approved') AND pm.kind != 'leftover'""")


def test_groups_and_breaks(app):
    with app.app_context():
        recipes = {r["name"]: r for r in store.recipes()}
        teriyaki = recipes["Chicken teriyaki rice bowl"]
        air = recipes["Air fryer garlic chicken & rice bowl"]
        hamburg = recipes["Hamburg steak with cabbage"]
        assert "chicken" in food_rules.recipe_groups(teriyaki)
        assert {"pork", "beef"} <= set(food_rules.recipe_groups(hamburg))
        rules = {"chicken": "airfryer"}
        assert food_rules.breaks(teriyaki, rules) and not food_rules.breaks(air, rules)
        assert food_rules.breaks(hamburg, {"pork": "never"})
        assert not food_rules.breaks(hamburg, {})


def test_air_fryer_only_chicken_fixes_the_plan(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        assert chicken_meals()
    client.post("/taste/rules", data={"rule_chicken": "airfryer", "rule_pork": "any"})
    with profile.app_context():
        s = store.settings()
        assert food_rules.load(s) == {"chicken": "airfryer"}
        assert "air_fryer" in s["appliances"]
        today = query("SELECT date('now')", one=True)[0]
        for m in chicken_meals():
            assert "air fry" in m["steps"].lower(), m["name"]


def test_never_pork_on_the_setup_form(profile, client):
    page = client.get("/setup/").get_data(as_text=True)
    assert "How you like each protein" in page and 'name="rule_chicken"' in page


def test_skipping_a_food_replans_meals_using_it(profile, client):
    client.post("/plan/generate")
    client.post("/plan/approve")
    with profile.app_context():
        first, _ = plans.current_week()
        row = query("""SELECT ri.food_id FROM plan_meals pm JOIN recipe_ingredients ri ON ri.recipe_id = pm.recipe_id
                       JOIN foods f ON f.id = ri.food_id WHERE f.category IN ('poultry', 'meat') AND pm.kind = 'cook'
                       AND pm.date >= date('now') LIMIT 1""", one=True)
        food = row["food_id"]
    client.post(f"/plan/shopping/skip/{food}")
    with profile.app_context():
        left = query("""SELECT COUNT(*) FROM plan_meals pm JOIN recipe_ingredients ri ON ri.recipe_id = pm.recipe_id
                        WHERE ri.food_id = ? AND pm.status IN ('draft', 'approved') AND pm.kind != 'leftover'
                        AND pm.date >= ? AND pm.date <= ?""",
                     (food, max(first, plans.get_today()).isoformat(), (first + __import__('datetime').timedelta(days=6)).isoformat()),
                     one=True)[0]
        assert left == 0
        assert not query("SELECT 1 FROM plan_meals WHERE status = 'draft' AND date BETWEEN ? AND ?",
                         (first.isoformat(), (first + __import__('datetime').timedelta(days=6)).isoformat()))


def test_shop_extra_guesses_a_price(profile, client):
    client.post("/plan/shopping/extra", data={"name": "ground beef", "amount": "500g"})
    client.post("/plan/shopping/extra", data={"name": "Chicken breast"})
    client.post("/plan/shopping/extra", data={"name": "birthday candles"})
    with profile.app_context():
        rows = {r["name"]: dict(r) for r in query("SELECT * FROM shopping_extra")}
        assert rows["ground beef"]["est_cost"] == 1250
        assert rows["Chicken breast"]["est_cost"] > 0 and rows["Chicken breast"]["amount"] == "about 300 g"
        assert rows["birthday candles"]["est_cost"] == 0


def test_air_fry_is_not_stove():
    from mealplanner.equipment import needs
    assert needs({"steps": "Air fry at 200 °C for 12 minutes."}) == {"air_fryer"}
    assert needs({"steps": "Press into panko."}) == set()
    assert needs({"steps": "Stir-fry the beef."}) == {"stove"}
