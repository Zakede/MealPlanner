import json
from datetime import date

from mealplanner import ask, llm, plans, store
from mealplanner.db import execute, query
from mealplanner.nutrition import day_target_parts, compute_targets
from mealplanner.schedule import fit_meal_times, slot_limits

THU = date(2026, 10, 8)


def _day(**kw):
    day = {"wake": "07:00", "breakfast_time": "07:30", "lunch_time": "12:30", "dinner_time": "19:00",
           "effort": "low", "away": 0, "blocks": []}
    day.update(kw)
    return day


def _block(label, start, end, commute=0):
    return {"label": label, "start": start, "end": end, "commute": commute}


def test_dinner_moves_after_the_gym_instead_of_being_packed():
    day = _day(blocks=[_block("Office", "09:00", "18:00", 20), _block("Gym", "18:00", "19:30")])
    notes = fit_meal_times(day)
    assert day["dinner_time"] == "20:00" and "Dinner 20:00, after Gym" in notes
    lim = slot_limits(day)
    assert not lim["dinner"]["away"] and 0 < lim["dinner"]["max_total"] <= 30     # a quick dinner at home


def test_early_shift_moves_breakfast_and_lunch():
    day = _day(blocks=[_block("Early shift", "05:00", "13:00", 20)])
    fit_meal_times(day)
    assert day["breakfast_time"] == "04:20" and day["wake"] <= "04:00"
    assert day["lunch_time"] == "13:35"
    assert not slot_limits(day)["lunch"]["away"]


def test_long_late_shift_keeps_dinner_packed():
    day = _day(blocks=[_block("Late shift", "16:00", "23:00")])
    assert fit_meal_times(day) == []
    assert slot_limits(day)["dinner"]["away"]


def test_overnight_shift_is_split_across_midnight(profile, client):
    resp = client.post(f"/plan/day/{THU.isoformat()}/activity",
                       data={"kind": "parttime", "label": "Night shift", "start": "22:00", "end": "06:00"},
                       follow_redirects=True)
    assert b"running into Friday morning" in resp.data
    with profile.app_context():
        rows = query("SELECT date, start, end FROM activities ORDER BY date")
    assert [tuple(r) for r in rows] == [("2026-10-08", "22:00", "23:59"), ("2026-10-09", "00:00", "06:00")]


def test_overlapping_activities_get_a_warning(profile, client):
    with profile.app_context():
        execute("UPDATE schedule_days SET work_start = '09:00', work_end = '18:00' WHERE weekday = 3")
    resp = client.post(f"/plan/day/{THU.isoformat()}/activity",
                       data={"kind": "club", "label": "Band", "start": "17:00", "end": "19:00"}, follow_redirects=True)
    assert b"Band overlaps Work" in resp.data


def test_target_parts_explain_the_number():
    t = compute_targets(85, 190, 25, "male", 1.3, 0.5, 78)
    kcal, _, parts = day_target_parts(t, True, 0, "male",
                                      work={"blocks": [("physical", 8)], "base_job": "desk"})
    labels = [p[0] for p in parts]
    assert labels[0] == "Your usual day" and "Gym" in labels and "Hard day: half the deficit back" in labels
    assert sum(k for _, k in parts) == kcal


def test_gym_only_as_activity_still_adds_food(profile, client):
    with profile.app_context():
        execute("UPDATE schedule_days SET gym = 0")
        plain = dict(plans.target_parts(THU))
    client.post(f"/plan/day/{THU.isoformat()}/activity", data={"kind": "gym", "start": "18:00", "end": "19:00"})
    with profile.app_context():
        parts = dict(plans.target_parts(THU))
    assert "Gym" in parts and "Gym" not in plain
    page = client.get(f"/plan/day/{THU.isoformat()}").data.decode()
    assert "Why this target" in page


def test_logged_workout_raises_todays_target(profile, client):
    with profile.app_context():
        execute("UPDATE schedule_days SET gym = 0")
    before = client.get("/").data.decode()
    assert "for today's workout" not in before
    with profile.app_context():
        execute("INSERT INTO workouts (date, kind, minutes, effort, kcal) VALUES ('2026-10-07', 'run', 40, 6, 420)")
    after = client.get("/").data.decode()
    assert "+210 for today's workout (420 burned" in after


def test_ask_knows_dishes_and_what_is_missing(profile):
    with profile.app_context():
        recipes = store.recipes()
    r = next(x for x in recipes if len(x["ingredients"]) >= 2)
    first, second = r["ingredients"][0], r["ingredients"][1]
    text = ask.recipe_context(f"I'm making {r['name']} and ran out of {first['name']}", recipes, [],
                              {second["id"]: second["grams"]}, set())
    assert r["name"] in text.splitlines()[0]                         # the dish list
    detail = next(line for line in text.splitlines() if line.startswith(f"- {r['name']} (asked about)"))
    assert f"{first['name']} {round(first['grams'])} g (MISSING)" in detail
    assert f"{second['name']} {round(second['grams'])} g (have)" in detail


class FakeAI:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt, images=(), model=None):
        self.prompts.append(prompt)
        return json.dumps({"answer": "Use Greek yogurt.", "ideas": [
            {"kind": "swap", "name": "Greek yogurt", "what": "Same amount", "why": "In your fridge", "kcal": 60}]})


def test_ran_out_on_the_cook_page_asks_with_context(profile, client, monkeypatch):
    ai = FakeAI()
    monkeypatch.setattr(llm, "provider", lambda: ai)
    client.post("/plan/generate")
    with profile.app_context():
        meal = next(m for m in plans.meals_between(THU, THU) if m["kind"] == "cook")
        r = store.recipe(meal["recipe_id"])
    page = client.get(f"/cook/{meal['id']}").data.decode()
    assert "Ran out of something?" in page
    resp = client.get("/recipes/ask", query_string={"dish": r["name"], "missing": r["ingredients"][0]["name"]})
    html = resp.data.decode()
    assert "Use Greek yogurt." in html and "Add to shopping list" in html
    prompt = ai.prompts[0]
    assert f"I'm making {r['name']}" in prompt and "kcal and" in prompt and "Their dishes:" in prompt
    assert f"- {r['name']} (asked about)" in prompt


def test_home_has_an_ask_box(profile, client):
    assert "Ask Zettai" in client.get("/").data.decode()
