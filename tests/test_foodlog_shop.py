import json
from datetime import date, timedelta

from mealplanner import plans, profiles, store
from mealplanner.db import query
from mealplanner.views.foodlog import check_estimate

WED = date(2026, 10, 7)
MON = date(2026, 10, 5)


def test_log_konbini_pick_counts_today_and_money(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        pan = query("SELECT * FROM quick_picks WHERE item = 'Curry pan'", one=True)
        spent = plans.week_budget(MON)["spent"]
    resp = client.post(f"/log/pick/{pan['id']}", data={"slot": "snack"}, follow_redirects=True)
    assert b"Logged Curry pan, 330 kcal" in resp.data
    with profile.app_context():
        assert plans.week_budget(MON)["spent"] == spent + 160
        snack = next(m for m in plans.meals_between(WED, WED) if m["slot"] == "snack")
        assert snack["status"] == "skipped"                      # replaced the planned snack
    home = client.get("/").data.decode()
    assert "Curry pan" in home and "logged" in home


def test_log_typed_food_and_delete(profile, client):
    client.post("/log/add", data={"mode": "manual", "name": "Onigiri from mom", "kcal": "210", "protein": "4",
                                  "slot": "lunch"})
    with profile.app_context():
        row = query("SELECT * FROM food_log", one=True)
        assert row["name"] == "Onigiri from mom" and row["slot"] == "lunch" and row["kcal"] == 210
    client.post(f"/log/{row['id']}/delete")
    with profile.app_context():
        assert not query("SELECT * FROM food_log")


def test_log_food_by_grams_and_recipe(profile, client):
    client.post("/log/add", data={"mode": "food", "food": "Banana", "grams": "120", "slot": "snack"})
    with profile.app_context():
        rid = query("SELECT id FROM recipes WHERE name = 'Oyakodon'", one=True)["id"]
    client.post("/log/add", data={"mode": "recipe", "recipe_id": rid, "portions": "0.5", "slot": "dinner"})
    with profile.app_context():
        rows = {r["source"]: r for r in query("SELECT * FROM food_log")}
        assert rows["food"]["kcal"] == round(86 * 1.2)
        assert rows["recipe"]["kcal"] == round(store.recipe(rid)["per_serving"]["kcal"] * 0.5)


def test_big_unplanned_food_rebalances_week(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        before = sum(m["kcal"] for m in plans.meals_between(WED + timedelta(days=1), MON + timedelta(days=6))
                     if m["status"] in plans.EDITABLE)
    client.post("/log/add", data={"mode": "manual", "name": "Ramen night", "kcal": "1500", "slot": "dinner"})
    with profile.app_context():
        after = sum(m["kcal"] for m in plans.meals_between(WED + timedelta(days=1), MON + timedelta(days=6))
                    if m["status"] in plans.EDITABLE)
    assert after < before


def test_check_estimate_keeps_only_sane_numbers():
    ok = check_estimate({"name": "Curry pan", "kcal": 330, "protein": 6.5, "carbs": 35, "fat": 18, "price": 160,
                         "confidence": "medium"})
    assert ok["kcal"] == 330 and ok["confidence"] == "medium"
    assert check_estimate({"kcal": -5}) is None and check_estimate({"kcal": "lots"}) is None
    silly = check_estimate({"name": "x", "kcal": 100, "protein": 90, "carbs": 90, "fat": 90})
    assert silly["protein"] == 0 and silly["fat"] == 0


def test_estimate_route_prefills_form(app, client):
    class Fake:
        model = "fake"

        def complete(self, prompt, images=(), model=None):
            assert "7-11 curry pan" in prompt
            return json.dumps({"name": "Curry pan", "kcal": 330, "protein": 6, "carbs": 36, "fat": 17, "price": 160,
                               "confidence": "medium"})
    app.config["LLM_PROVIDER"] = Fake()
    page = client.post("/log/estimate", data={"text": "7-11 curry pan"}).data.decode()
    assert 'value="Curry pan"' in page and 'value="330"' in page and "medium confidence" in page


def test_log_page_renders(client):
    page = client.get("/log/").data.decode()
    assert "Konbini" in page and "Famichiki" in page


def test_shopping_skip_add_back_and_extras(profile, client):
    client.post("/plan/generate")
    client.post("/plan/approve")
    with profile.app_context():
        item = plans.shopping_list(MON)[0]
    client.post(f"/plan/shopping/skip/{item['food_id']}")
    with profile.app_context():
        assert item["food_id"] not in {i["food_id"] for i in plans.shopping_list(MON)}
        plans.build_shopping_list(MON)                         # stays skipped after a rebuild
        assert item["food_id"] not in {i["food_id"] for i in plans.shopping_list(MON)}
    client.post(f"/plan/shopping/skip/{item['food_id']}", data={"undo": "1"})
    with profile.app_context():
        # meals were re-planned without it, so it's simply allowed again (no longer on the skip list)
        assert item["food_id"] not in plans.skipped_foods(MON)
    client.post("/plan/shopping/extra", data={"name": "Coffee beans", "amount": "1 bag", "cost": "900"})
    with profile.app_context():
        extra = plans.shopping_extras(MON)[0]
        assert extra["name"] == "Coffee beans" and plans.week_budget(MON)["planned"] >= 900
    client.post(f"/plan/shopping/extra/{extra['id']}/toggle")
    client.post(f"/plan/shopping/extra/{extra['id']}/delete")
    with profile.app_context():
        assert not plans.shopping_extras(MON)
    page = client.get("/plan/shopping").data.decode()
    assert "Meat &amp; fish" in page or "Vegetables" in page


def test_buy_amounts():
    from mealplanner.views.plan import buy_amount
    assert buy_amount({"grams": 130, "piece_g": 60}) == "3 pcs"
    assert buy_amount({"grams": 130, "piece_g": None}) == "150 g"
    assert buy_amount({"grams": 620, "piece_g": None}) == "700 g"


def test_setup_sets_profile_name_and_password(app, client):
    from tests.test_preferences import wizard_form
    client.post("/setup/", data=wizard_form(profile_name="Mannat", password="fujiiro1", again="fujiiro1"))
    with app.app_context():
        assert profiles.find("main")["name"] == "Mannat"
        assert store.settings()["password_hash"]
    assert client.get("/more").status_code == 200          # stays logged in on this device


def test_setup_rejects_mismatched_password(client):
    from tests.test_preferences import wizard_form
    resp = client.post("/setup/", data=wizard_form(password="fujiiro1", again="nope"), follow_redirects=True)
    assert b"must match" in resp.data


def test_shopping_for_one_day(profile, client):
    from mealplanner import plans
    client.post("/plan/generate")
    page = client.get("/plan/shopping").data.decode()
    assert "Buy for" in page and "Today" in page and "Tomorrow" in page
    with profile.app_context():
        first, _ = plans.current_week()
        today_items = plans.day_shopping(first, plans.get_today())
        week = plans.shopping_needs(first, statuses=("draft", "approved"))
    assert today_items and all(i["food_id"] in week for i in today_items)
    assert all(i["grams"] <= week[i["food_id"]]["grams"] + 1 for i in today_items)
    day_page = client.get(f"/plan/shopping?day={plans_today(profile)}").data.decode()
    assert "for today" in day_page
    item = today_items[0]
    client.post(f"/plan/shopping/day-bought/{item['food_id']}?day={plans_today(profile)}",
                data={"grams": item["grams"], "est": item["est_cost"], "price": ""})
    with profile.app_context():
        after = {i["food_id"] for i in plans.day_shopping(first, plans.get_today())}
        assert item["food_id"] not in after          # bought, so today no longer needs it


def plans_today(app):
    return app.config["TODAY"]



def test_already_have_an_item_on_the_shopping_list(profile, client):
    client.post("/plan/generate")
    client.post("/plan/approve")
    with profile.app_context():
        item = query("SELECT * FROM shopping_list WHERE week_start = ? AND checked = 0 LIMIT 1",
                     (MON.isoformat(),), one=True)
        spent = plans.week_budget(MON)["spent"]
    page = client.get("/plan/shopping").data.decode()
    assert "Have it" in page
    resp = client.post(f"/plan/shopping/have/{item['food_id']}", data={"grams": item["grams"]}, follow_redirects=True)
    assert b"Added to your pantry, not to spending" in resp.data
    with profile.app_context():
        assert query("SELECT checked FROM shopping_list WHERE id = ?", (item["id"],), one=True)["checked"] == 1
        assert query("SELECT price_paid FROM pantry_items WHERE food_id = ? ORDER BY id DESC",
                     (item["food_id"],), one=True)["price_paid"] == 0
        assert plans.week_budget(MON)["spent"] == spent           # not counted as money spent


def test_finish_shopping_saves_everything_at_once(profile, client):
    client.post("/plan/generate")
    client.post("/plan/approve")
    with profile.app_context():
        items = [dict(r) for r in query("SELECT * FROM shopping_list WHERE week_start = ? AND checked = 0 LIMIT 3",
                                        (MON.isoformat(),))]
        spent = plans.week_budget(MON)["spent"]
    page = client.get("/plan/shopping").data.decode()
    assert "Finish shopping" in page and ("What&#39;s this?" in page or "What's this?" in page)
    a, b, c = items
    data = {f"act_{a['food_id']}": "bought", f"grams_{a['food_id']}": a["grams"], f"est_{a['food_id']}": a["est_cost"],
            f"price_{a['food_id']}": "500",
            f"act_{b['food_id']}": "have", f"grams_{b['food_id']}": b["grams"], f"est_{b['food_id']}": b["est_cost"],
            f"act_{c['food_id']}": "skip", f"grams_{c['food_id']}": c["grams"], f"est_{c['food_id']}": c["est_cost"]}
    resp = client.post("/plan/shopping/finish", data=data, follow_redirects=True)
    assert b"Shopping saved: 1 bought, 1 already at home, 1 skipped" in resp.data
    with profile.app_context():
        assert plans.week_budget(MON)["spent"] == spent + 500
        assert c["food_id"] in plans.skipped_foods(MON)
        left = {r["food_id"] for r in query("SELECT food_id FROM shopping_list WHERE week_start = ? AND checked = 0",
                                            (MON.isoformat(),))}
        assert not left & {a["food_id"], b["food_id"], c["food_id"]}


def test_whats_this_without_ai_still_explains(profile, client):
    with profile.app_context():
        food = query("SELECT id, name FROM foods WHERE category = 'soy' LIMIT 1", one=True)
    data = client.get(f"/plan/food-info/{food['id']}").get_json()
    assert food["name"] in data["text"] and "soy" in data["text"]
