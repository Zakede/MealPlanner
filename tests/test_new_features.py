from datetime import date

from mealplanner import store, units
from mealplanner.db import execute, query
from mealplanner.library import FOODS, RECIPES, TASTE_GUIDE


def test_library_has_discoveries_and_many_condiments():
    names = {f[0] for f in FOODS}
    assert {"Canned kidney beans", "Red lentils (dry)", "Canned mackerel"} <= names
    assert any(r[0] == "Kidney bean chili bowl (batch)" for r in RECIPES)
    total = sum(len(sec[4]) for sec in TASTE_GUIDE)
    assert total >= 150
    keys = [sec[0] for sec in TASTE_GUIDE]
    assert {"world", "rub", "crunch", "dips"} <= set(keys)
    all_names = [i[0].lower() for sec in TASTE_GUIDE for i in sec[4]]
    assert len(all_names) == len(set(all_names))


def test_home_suggests_something_new(profile, client):
    page = client.get("/").data.decode()
    assert "Try something new" in page and "What about" in page
    nxt = client.get("/?idea=1").data.decode()
    assert "What about" in nxt


def test_suggestion_respects_diet(profile, client):
    with profile.app_context():
        execute("UPDATE settings SET diet = 'vegan' WHERE id = 1")
    for n in range(14):
        page = client.get(f"/?idea={n}").data.decode()
        assert "mackerel" not in page.lower().split("try something new")[-1][:400]


def test_own_condiments(profile, client):
    client.post("/recipes/boosters/mine", data={"name": "Mum's chili oil", "kcal": "40", "serving": "1 tsp",
                                                 "use": "Noodles", "yen": "300"})
    page = client.get("/recipes/boosters").data.decode()
    assert "Mum&#39;s chili oil" in page or "Mum's chili oil" in page
    client.post("/recipes/boosters/add", data={"name": "Mum's chili oil"})
    with profile.app_context():
        assert query("SELECT 1 FROM shopping_extra WHERE name = ?", ("Mum's chili oil",), one=True)
        rid = query("SELECT id FROM my_condiments", one=True)["id"]
    client.post(f"/recipes/boosters/mine/{rid}/delete")
    with profile.app_context():
        assert not query("SELECT 1 FROM my_condiments")


def test_imperial_setup_and_display(app, client):
    client.post("/setup/", data={"profile_name": "Deisy", "units": "imperial", "sex": "female", "age": "24",
                                 "height_ft": "5", "height_in": "4", "weight_lb": "130", "goal_lb": "120",
                                 "pace_kg_week": "0.25", "training_days": "0", "weekly_budget_yen": "8000", "commute_min": "30",
                                 "eat_out_slots": "1", "eat_out_budget_yen": "1000", "spice_tolerance": "2"})
    with app.app_context():
        s = store.settings()
        assert s["units"] == "imperial"
        assert abs(s["height_cm"] - 162.6) < 0.2 and abs(s["weight_kg"] - 59.0) < 0.1
    with app.test_request_context():
        from flask import session
        session["profile"] = "main"
        assert units.temps("Air fry at 200 °C until golden") == "Air fry at 390 °F until golden"
        assert units.amount(150) == "5.3 oz"
        assert units.body(59.0) == 130.1
    page = client.get("/progress").data.decode()
    assert " lb" in page


def test_progress_shows_money_food_and_habits(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        mid = query("SELECT id FROM plan_meals WHERE date = '2026-10-07' LIMIT 1", one=True)["id"]
        execute("UPDATE plan_meals SET status = 'eaten' WHERE id = ?", (mid,))
        execute("INSERT INTO water_log (date, ml) VALUES ('2026-10-07', 3500)")
        execute("INSERT INTO eating_out_log (date, slot, kcal, yen) VALUES ('2026-10-06', 'lunch', 700, 1100)")
    page = client.get("/progress").data.decode()
    for word in ("Spent on food", "Average a day", "Protein a day", "Meals cooked", "Habits", "Day by day"):
        assert word in page
    assert "1,100" in page
    assert client.get("/progress?span=30").status_code == 200


def test_flexible_mode_keeps_schedule_work(profile):
    from mealplanner import plans
    with profile.app_context():
        execute("UPDATE settings SET schedule_mode = 'flexible' WHERE id = 1")
        execute("UPDATE schedule_days SET work_start = NULL, work_end = NULL")
        execute("UPDATE schedule_days SET work_start = '10:00', work_end = '19:00' WHERE weekday = 3")
        thu = date(2026, 10, 8)
        day = plans.build_days([thu])[thu]
        assert day["work_start"] == "10:00" and day["blocks"][0]["kind"] == "work"


def test_adding_work_replaces_usual_work(profile, client):
    from mealplanner import plans
    client.post("/plan/day/2026-10-08/activity", data={"kind": "work", "start": "12:00", "end": "20:00"})
    with profile.app_context():
        thu = date(2026, 10, 8)
        blocks = plans.build_days([thu])[thu]["blocks"]
        assert [(b["start"], b["end"]) for b in blocks if b["kind"] == "work"] == [("12:00", "20:00")]


def test_workouts_page_types_repeats_and_gym_day(profile, client):
    page = client.get("/workouts").data.decode()
    for word in ("Yoga", "Boxing", "Jump rope", "Ideas by time", "Nothing logged yet"):
        assert word in page
    client.post("/workouts", data={"date": "2026-10-07", "kind": "yoga", "minutes": "30", "effort": "4", "feed": "1"})
    with profile.app_context():
        from mealplanner import plans
        assert plans.override(date(2026, 10, 7))["gym"] == 1
        assert query("SELECT kind FROM workouts", one=True)["kind"] == "yoga"
    page = client.get("/workouts").data.decode()
    assert "Do it again" in page and "+ today" in page and "1<small" in page
