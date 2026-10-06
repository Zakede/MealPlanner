from datetime import date, timedelta

import pytest

from mealplanner import cooking, plans, store
from mealplanner.db import execute, query

WED = date(2026, 10, 7)
MON = date(2026, 10, 5)


def add_pantry(client, name, qty, expiry=None, unit="g", price="100"):
    food_values = {"Egg": ("142", "12.2", "0.4", "10.2"), "Firm tofu": ("73", "7", "1.5", "4.9")}
    kcal, p, c, f = food_values.get(name, ("100", "10", "10", "1"))
    client.post("/pantry/new", data={"name": name, "quantity": str(qty), "unit": unit, "price_paid": price,
                                     "expiry": expiry or "", "location": "fridge",
                                     "kcal": kcal, "protein": p, "carbs": c, "fat": f})


def test_step_timer():
    assert cooking.step_timer("Boil for 8 minutes") == 8
    assert cooking.step_timer("Grill the salmon 8-10 minutes until it flakes") == 10
    assert cooking.step_timer("Mix everything") is None


def test_deduct_uses_soonest_expiry_first(app, client):
    add_pantry(client, "Firm tofu", 300, "2026-10-12")
    add_pantry(client, "Firm tofu", 200, "2026-10-08")
    with app.app_context():
        tofu = store.food_by_name("Firm tofu")
        short = cooking.deduct(tofu["id"], 250, WED)
        assert short == 0
        left = {r["expiry"]: r["quantity"] for r in query("SELECT * FROM pantry_items")}
        assert left == {"2026-10-12": 250}


def test_deduct_skips_expired_and_reports_shortfall(app, client):
    add_pantry(client, "Firm tofu", 300, "2026-10-01")
    with app.app_context():
        tofu = store.food_by_name("Firm tofu")
        assert cooking.deduct(tofu["id"], 100, WED) == 100


def test_deduct_pieces(app, client):
    add_pantry(client, "Egg", 10, unit="pcs")
    with app.app_context():
        egg = store.food_by_name("Egg")
        cooking.deduct(egg["id"], 120, WED)  # two eggs
        assert query("SELECT quantity FROM pantry_items", one=True)["quantity"] == 8


def batch_meal(app):
    with app.app_context():
        meals = plans.meals_between(MON, MON + timedelta(days=6))
        return next((m for m in meals if m["kind"] == "cook" and m["cook_portions"] > m["portion"]), None)


def make_batch_plan(profile):
    """Force a batch cook on Wednesday dinner so the leftover flow can be tested."""
    with profile.app_context():
        execute("UPDATE schedule_days SET effort = 'full', work_start = NULL, work_end = NULL WHERE weekday = 2")
        plans.generate_week(MON)


def test_finish_cooking_creates_leftovers_linked_to_plan(profile):
    make_batch_plan(profile)
    meal = batch_meal(profile)
    assert meal, "expected a batch cook in the plan"
    with profile.app_context():
        result = cooking.finish_cooking(meal)
        assert result["leftover_portions"] == pytest.approx(meal["cook_portions"] - meal["portion"])
        lo = query("SELECT * FROM leftovers", one=True)
        assert lo["portions"] == pytest.approx(result["leftover_portions"])
        assert lo["safe_until"] == (WED + timedelta(days=meal["recipe"]["fridge_days"])).isoformat() \
            or lo["cooked_on"] == WED.isoformat()
        linked = query("SELECT * FROM plan_meals WHERE cook_group = ?", (meal["id"],))
        assert linked and all(r["leftover_id"] == lo["id"] for r in linked)
        assert query("SELECT status FROM plan_meals WHERE id = ?", (meal["id"],), one=True)["status"] == "cooked"


def test_eating_leftover_reduces_portions(profile):
    make_batch_plan(profile)
    meal = batch_meal(profile)
    with profile.app_context():
        cooking.finish_cooking(meal)
        lmeal = dict(query("SELECT * FROM plan_meals WHERE cook_group = ?", (meal["id"],), one=True))
        before = query("SELECT portions FROM leftovers", one=True)["portions"]
        cooking.eat(lmeal)
        after = query("SELECT portions FROM leftovers", one=True)["portions"]
        assert after == pytest.approx(before - lmeal["portion"])


def test_freezing_extends_safe_date(profile):
    make_batch_plan(profile)
    meal = batch_meal(profile)
    with profile.app_context():
        result = cooking.finish_cooking(meal)
        cooking.freeze_leftover(result["leftover_id"])
        lo = query("SELECT * FROM leftovers", one=True)
        assert lo["location"] == "freezer"
        assert lo["safe_until"] == (WED + timedelta(days=cooking.FREEZER_DAYS)).isoformat()


def test_skip_cascades_and_undo_restores(profile):
    make_batch_plan(profile)
    meal = batch_meal(profile)
    with profile.app_context():
        n = cooking.skip(meal)
        assert n >= 2
        statuses = {r["status"] for r in query("SELECT status FROM plan_meals WHERE id = ? OR cook_group = ?",
                                                (meal["id"], meal["id"]))}
        assert statuses == {"skipped"}
        plans.undo_last()
        statuses = {r["status"] for r in query("SELECT status FROM plan_meals WHERE id = ? OR cook_group = ?",
                                                (meal["id"], meal["id"]))}
        assert statuses == {"draft"}


def test_cook_pages(profile, client):
    make_batch_plan(profile)
    meal = batch_meal(profile)
    page = client.get(f"/cook/{meal['id']}")
    assert page.status_code == 200 and b"Done cooking" in page.data
    resp = client.post(f"/cook/{meal['id']}/done", follow_redirects=True)
    assert b"saved as leftovers" in resp.data
    assert b"Already logged" in client.post(f"/cook/{meal['id']}/done", follow_redirects=True).data
    assert client.get("/cook/leftovers").status_code == 200


def test_eaten_meal_counts_on_home(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        bf = next(m for m in plans.meals_between(WED, WED) if m["slot"] == "breakfast")
    client.post(f"/cook/{bf['id']}/done")
    page = client.get("/").data.decode()
    assert "✓" in page
