from datetime import date, timedelta

import pytest

from mealplanner import budget, plans, store
from mealplanner.db import execute, query
from mealplanner.planner import PantrySim, best_portion, konbini_combo

WED = date(2026, 10, 7)
MON = date(2026, 10, 5)


def week_meals(app):
    with app.app_context():
        return plans.meals_between(MON, MON + timedelta(days=6))


def generate(app):
    with app.app_context():
        return plans.generate_week(MON)


# pure helpers

def test_week_bounds():
    assert budget.week_bounds(WED) == (MON, MON + timedelta(days=6))
    assert budget.week_bounds(MON)[0] == MON


def test_budget_status():
    st = budget.status(10000, spent=6000, planned=2500, reserved=1200)
    assert st["remaining"] == 4000 and st["after_plan"] == 300 and not st["over"]
    assert budget.status(10000, 9000, 2000)["over"]


def test_grocery_cap_never_negative():
    assert budget.grocery_cap(5000, 6000, 1200) == 0
    assert budget.grocery_cap(10000, 3000, budget.reserved_eat_out(2, 1, 1200)) == 5800


def test_pantry_sim_uses_oldest_first_and_skips_expired():
    sim = PantrySim([(1, 200, WED + timedelta(days=5)), (1, 100, WED + timedelta(days=1)),
                     (1, 500, WED - timedelta(days=1))])
    have, missing, expiring = sim.check(1, 250, WED)
    assert have == 250 and missing == 0 and expiring == 100
    assert sim.take(1, 350, WED) == 50


def test_best_portion():
    assert best_portion(400, 600) == 1.5
    assert best_portion(400, 90) == 0.5


def test_konbini_combo_respects_budget_and_kcal():
    picks = [{"chain": "Konbini", "item": "chicken", "kcal": 115, "protein": 24, "yen": 298},
             {"chain": "Konbini", "item": "onigiri", "kcal": 180, "protein": 4.5, "yen": 180},
             {"chain": "McDonald's", "item": "burger", "kcal": 256, "protein": 12.8, "yen": 200}]
    combo = konbini_combo(picks, 300, 1000)
    assert [p["item"] for p in combo["items"]] == ["chicken", "onigiri"]
    assert konbini_combo(picks, 300, 100)["items"] == []


# planner against the database

def test_plan_needs_profile(app):
    with app.app_context(), pytest.raises(ValueError):
        plans.generate_week(MON)


def test_generate_fills_rest_of_week(profile):
    meals = generate(profile)
    dates = {m["date"] for m in meals}
    assert min(dates) == WED and max(dates) == MON + timedelta(days=6)
    for d in dates:
        slots = {m["slot"] for m in meals if m["date"] == d}
        assert {"breakfast", "lunch", "dinner"} <= slots
    assert all(m["status"] == "draft" for m in meals)


def test_daily_calories_near_target(profile):
    generate(profile)
    with profile.app_context():
        for d in plans.day_summaries(MON):
            if d["meals"] and d["target"]:
                assert d["kcal"] <= d["target"]["kcal_target"] * 1.15
                assert d["kcal"] >= d["target"]["kcal_target"] * 0.6


def test_allergies_are_never_planned(profile):
    with profile.app_context():
        execute("UPDATE settings SET allergies = 'egg, fish' WHERE id = 1")
    generate(profile)
    with profile.app_context():
        for m in plans.meals_between(MON, MON + timedelta(days=6)):
            if m["recipe"]:
                assert "egg" not in m["recipe"]["allergens"] and "fish" not in m["recipe"]["allergens"]


def test_spice_tolerance_filters(profile):
    with profile.app_context():
        execute("UPDATE settings SET spice_tolerance = 1 WHERE id = 1")
    generate(profile)
    for m in week_meals(profile):
        if m["recipe"]:
            assert m["recipe"]["spice_level"] <= 1


def test_budget_is_a_hard_limit(profile):
    with profile.app_context():
        execute("UPDATE settings SET weekly_budget_yen = 3000, eat_out_slots = 0 WHERE id = 1")
    generate(profile)
    with profile.app_context():
        total = sum(m["buy_cost"] for m in plans.meals_between(MON, MON + timedelta(days=6)))
        assert total <= 3000


def test_zero_budget_uses_pantry_only(profile):
    with profile.app_context():
        execute("UPDATE settings SET weekly_budget_yen = 0, eat_out_slots = 0 WHERE id = 1")
    meals = generate(profile)
    assert sum(m["buy_cost"] for m in meals) == 0


def test_eat_out_slot_reserved(profile):
    meals = generate(profile)
    eat_out = [m for m in meals if m["kind"] == "eat_out"]
    assert len(eat_out) == 1 and eat_out[0]["kcal"] == 800


def test_work_lunches_avoid_konbini(profile):
    meals = generate(profile)
    work_lunches = [m for m in meals if m["slot"] == "lunch" and m["date"].weekday() < 5]
    assert work_lunches
    konbini = [m for m in work_lunches if m["kind"] == "konbini"]
    assert len(konbini) < len(work_lunches)
    for m in work_lunches:
        if m["kind"] in ("cook", "nocook"):
            assert m["recipe"]["portable"]


def test_batch_cook_creates_leftover_meals(profile):
    generate(profile)
    meals = week_meals(profile)
    groups = {m["cook_group"] for m in meals if m["kind"] == "leftover" and m["cook_group"]}
    for g in groups:
        cook = next(m for m in meals if m["id"] == g)
        portions = [m["portion"] for m in meals if m["cook_group"] == g]
        assert cook["cook_portions"] == pytest.approx(cook["portion"] + sum(portions))


def test_expiring_pantry_item_is_used(profile, client):
    client.post("/pantry/new", data={"name": "Firm tofu", "quantity": "300", "unit": "g", "price_paid": "90",
                                     "expiry": "2026-10-08", "location": "fridge", "kcal": "73",
                                     "protein": "7", "carbs": "1.5", "fat": "4.9"})
    meals = generate(profile)
    early = [m for m in meals if m["date"] <= date(2026, 10, 8) and m.get("recipe")]
    assert any("Firm tofu" in [i["name"] for i in m["recipe"]["ingredients"]] for m in early)


def test_replace_swaps_marked_meal(profile):
    generate(profile)
    with profile.app_context():
        target = next(m for m in plans.meals_between(MON, MON + timedelta(days=6))
                      if m["kind"] in ("cook", "nocook") and m["slot"] == "breakfast")
        plans.set_replace(target["id"], True)
        plans.replace_flagged(MON)
        after = [m for m in plans.meals_between(target["date"], target["date"]) if m["slot"] == "breakfast"]
        assert len(after) == 1 and after[0]["recipe_id"] != target["recipe_id"]


def test_approve_builds_shopping_list(profile):
    generate(profile)
    with profile.app_context():
        plans.approve_week(MON)
        assert all(m["status"] == "approved" for m in plans.meals_between(WED, MON + timedelta(days=6)))
        items = plans.shopping_list(MON)
        assert items and all(i["est_cost"] >= 0 for i in items)
        st = plans.week_budget(MON)
        assert st["planned"] == pytest.approx(sum(i["est_cost"] for i in items)
                                              + sum(m["buy_cost"] for m in plans.meals_between(MON, MON + timedelta(days=6))
                                                    if m["kind"] == "konbini"), abs=2)


def test_bought_item_moves_to_pantry_and_counts_as_spent(profile):
    generate(profile)
    with profile.app_context():
        plans.approve_week(MON)
        item = plans.shopping_list(MON)[0]
        plans.add_bought_to_pantry(MON, item["id"], 500)
        assert plans.week_budget(MON)["spent"] == 500
        assert query("SELECT COUNT(*) c FROM pantry_items", one=True)["c"] == 1


def test_push_back_and_undo(profile):
    generate(profile)
    with profile.app_context():
        before = {m["id"]: m["date"] for m in plans.meals_between(MON, MON + timedelta(days=13))}
        plans.push_back(2)
        after = {m["id"]: m["date"] for m in plans.meals_between(MON, MON + timedelta(days=13))}
        moved = [i for i in before if after[i] != before[i]]
        assert moved
        for i in moved:
            assert after[i] == before[i] + timedelta(days=2)
        # breakfast and lunch today stay where they are
        today_early = [m for m in plans.meals_between(WED, WED) if m["slot"] in ("breakfast", "lunch")]
        assert all(after[m["id"]] == WED for m in today_early)
        plans.undo_last()
        restored = {m["id"]: m["date"] for m in plans.meals_between(MON, MON + timedelta(days=13))}
        assert restored == before


def test_settings_change_replans(profile, client):
    generate(profile)
    with profile.app_context():
        before = sum(m["kcal"] for m in plans.meals_between(WED, WED + timedelta(days=4)))
    data = {"units": "metric", "height_cm": "190", "weight_kg": "85", "goal_weight_kg": "78", "age": "25",
            "sex": "male", "activity": "sedentary", "pace_kg_week": "0.75", "weekly_budget_yen": "10000",
            "eat_out_slots": "1", "eat_out_budget_yen": "1200", "eat_out_kcal": "800", "snack_kcal": "200",
            "spice_tolerance": "4", "allergies": "", "dislikes": "", "flavor_likes": "", "cuisines_liked": "",
            "cuisines_tired": ""}
    resp = client.post("/settings/", data=data, follow_redirects=True)
    assert b"plan was updated" in resp.data
    with profile.app_context():
        after = sum(m["kcal"] for m in plans.meals_between(WED, WED + timedelta(days=4)))
    assert after < before


def test_plan_pages_render(profile, client):
    generate(profile)
    for url in ("/plan/", "/plan/?week=next", "/plan/shopping", "/plan/api/week"):
        assert client.get(url).status_code == 200
    assert client.post("/plan/approve", follow_redirects=True).status_code == 200
