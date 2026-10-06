from datetime import date, timedelta

import pytest

from mealplanner import logbook, plans
from mealplanner.db import execute, query
from mealplanner.extras import best_picks, combo_for, spread_excess, workout_kcal

WED = date(2026, 10, 7)
MON = date(2026, 10, 5)
SUN = MON + timedelta(days=6)

PICKS = [
    {"chain": "Konbini", "item": "Salad chicken", "kcal": 115, "protein": 24, "yen": 298},
    {"chain": "Konbini", "item": "Onigiri", "kcal": 180, "protein": 4.5, "yen": 180},
    {"chain": "Konbini", "item": "Boiled egg", "kcal": 80, "protein": 6.5, "yen": 98},
    {"chain": "McDonald's", "item": "Double cheeseburger", "kcal": 457, "protein": 26.5, "yen": 430},
]


def test_workout_kcal_scales_with_effort_and_weight():
    easy = workout_kcal("weights", 60, 1, 85)
    hard = workout_kcal("weights", 60, 10, 85)
    assert easy == round(2.5 * 85) and hard == round(5.0 * 85)
    assert workout_kcal("running", 30, 5, 70) < workout_kcal("running", 30, 5, 90)
    assert workout_kcal("unknown", 30, 5, 80) == workout_kcal("other", 30, 5, 80)


def test_best_picks_fit_room_and_rank_by_protein_density():
    picks = best_picks(PICKS, 200)
    assert [p["item"] for p in picks] == ["Salad chicken", "Boiled egg", "Onigiri"]


def test_combo_stays_under_room():
    combo = combo_for(PICKS[:3], 300)
    assert combo["kcal"] <= 300 and combo["items"][0]["item"] == "Salad chicken"


def test_spread_drops_snacks_first_then_trims():
    d1, d2 = WED + timedelta(days=1), WED + timedelta(days=2)
    meals = [{"id": 1, "date": d1, "kind": "snack", "kcal": 150, "portion": 1},
             {"id": 2, "date": d1, "kind": "cook", "kcal": 700, "portion": 1},
             {"id": 3, "date": d2, "kind": "cook", "kcal": 600, "portion": 1}]
    totals = {d1: 2000, d2: 1900}
    floors = {d1: 1500, d2: 1500}
    actions, left = spread_excess(400, meals, totals, floors)
    assert actions[0] == ("drop", 1)
    scaled = [a for a in actions if a[0] == "scale"]
    assert all(a[2] >= 0.8 for a in scaled)
    assert left == 0


def test_spread_respects_floor():
    d1 = WED + timedelta(days=1)
    meals = [{"id": 1, "date": d1, "kind": "cook", "kcal": 700, "portion": 1}]
    actions, left = spread_excess(500, meals, {d1: 1550}, {d1: 1500})
    assert actions == [("scale", 1, pytest.approx(1 - 50 / 700, abs=0.001))]
    assert left == 450


def test_unplanned_meal_out_rebalances_week(profile):
    with profile.app_context():
        plans.generate_week(MON)
        before = sum(m["kcal"] for m in plans.meals_between(WED + timedelta(days=1), SUN)
                     if m["status"] in plans.EDITABLE)
        notes = logbook.log_eat_out(WED, "lunch", "Ramen shop", "Tonkotsu", 1300, 30, 1100)
        lunch = [m for m in plans.meals_between(WED, WED) if m["slot"] == "lunch"]
        assert lunch[0]["status"] == "eaten_out"
        after = sum(m["kcal"] for m in plans.meals_between(WED + timedelta(days=1), SUN)
                    if m["status"] in plans.EDITABLE)
        assert after < before
        assert any("Balanced" in n for n in notes)
        log = query("SELECT * FROM eating_out_log", one=True)
        assert log["planned"] == 1  # used the week's reserved slot
        assert not [m for m in plans.meals_between(MON, SUN) if m["kind"] == "eat_out" and m["status"] in plans.EDITABLE]
        assert plans.week_budget(MON)["spent"] == 1100


def test_meal_out_in_reserved_slot(profile):
    with profile.app_context():
        plans.generate_week(MON)
        reserved = next(m for m in plans.meals_between(MON, SUN) if m["kind"] == "eat_out")
        logbook.log_eat_out(reserved["date"], reserved["slot"], "Matsuya", "Gyumeshi", 700, 25, 600)
        assert query("SELECT status FROM plan_meals WHERE id = ?", (reserved["id"],), one=True)["status"] == "eaten_out"
        assert query("SELECT planned FROM eating_out_log", one=True)["planned"] == 1


def test_spending_compares_paid_and_estimate(app, client):
    client.post("/pantry/new", data={"name": "Chicken breast", "quantity": "500", "unit": "g", "price_paid": "500",
                                     "location": "fridge", "kcal": "105", "protein": "23.3", "carbs": "0", "fat": "1.9"})
    with app.app_context():
        sp = logbook.spending(MON)
        item = sp["bought"][0]
        assert item["price_paid"] == 500 and item["estimate"] == 425   # 500 g at the ¥85 reference
        assert sp["groceries"] == 500 and sp["estimated"] == 425


def test_price_changes(app):
    with app.app_context():
        execute("INSERT INTO price_history (food_id, price_per_100g, recorded_on) VALUES (1, 80, '2026-09-01')")
        execute("INSERT INTO price_history (food_id, price_per_100g, recorded_on) VALUES (1, 100, '2026-10-01')")
        changes = logbook.price_changes()
        assert changes[0]["change"] == pytest.approx(0.25)


def test_workout_log_and_pages(app, client):
    resp = client.post("/workouts", data={"date": "2026-10-07", "kind": "weights", "minutes": "60", "effort": "10"},
                       follow_redirects=True)
    assert b"about 425 kcal" in resp.data
    client.post("/workouts", data={"date": "2026-10-07", "kind": "running", "minutes": "30", "kcal": "350"})
    with app.app_context():
        rows = query("SELECT * FROM workouts ORDER BY id")
        assert rows[1]["kcal"] == 350 and rows[1]["kcal_estimated"] == 0
    for url in ("/snacks", "/eat-out", "/eat-out?kcal=400", "/spending", "/workouts"):
        assert client.get(url).status_code == 200


def test_add_and_delete_swap(app, client):
    client.post("/snacks", data={"craving": "Donut", "swap": "Rice cake with honey", "kcal_from": "300", "kcal_to": "120"})
    with app.app_context():
        sid = query("SELECT id FROM craving_swaps WHERE craving = 'Donut'", one=True)["id"]
    client.post(f"/snacks/{sid}/delete")
    with app.app_context():
        assert query("SELECT COUNT(*) c FROM craving_swaps WHERE craving = 'Donut'", one=True)["c"] == 0


def test_eat_out_form_validation(client):
    resp = client.post("/eat-out", data={"slot": "dinner", "kcal": ""}, follow_redirects=True)
    assert b"Kcal is required" in resp.data
