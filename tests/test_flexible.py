import json
from datetime import date, timedelta

from mealplanner import plans, store
from mealplanner.db import execute, query
from mealplanner.equipment import can_make, needs
from mealplanner.views.setup import apply_description

MON = date(2026, 10, 5)
WED = date(2026, 10, 7)
SUN = MON + timedelta(days=6)


def recipe(app, name):
    with app.app_context():
        return store.recipe(query("SELECT id FROM recipes WHERE name = ?", (name,), one=True)["id"])


def test_equipment_guessed_from_steps(app):
    stir_fry = recipe(app, "Ginger pork with cabbage")
    oats = recipe(app, "Protein overnight oats")
    toast = recipe(app, "Egg & cheese toast")
    assert needs(stir_fry) == {"stove"} and needs(oats) == set()
    assert "toaster_oven" in needs(toast)
    assert can_make(stir_fry, {"stove"}) and not can_make(stir_fry, {"microwave"})
    assert can_make(toast, {"stove", "oven"})            # a full oven does what a toaster oven does
    assert can_make(oats, set())


def test_microwave_only_kitchen_plans_without_stove(profile):
    with profile.app_context():
        execute("UPDATE settings SET appliances = 'microwave,rice_cooker' WHERE id = 1")
        plans.generate_week(MON)
        for m in plans.meals_between(WED, SUN):
            if m["recipe"]:
                assert "stove" not in needs(m["recipe"]), m["title"]


def test_flexible_mode_spreads_prep_days(profile):
    with profile.app_context():
        execute("UPDATE settings SET schedule_mode = 'flexible', prep_days = 2 WHERE id = 1")
        dates = [WED + timedelta(days=i) for i in range(5)]
        days = plans.build_days(dates)
        prep = [d for d in dates if days[d]["effort"] == "full"]
        assert len(prep) == 2 and prep[0] == WED
        assert all(days[d]["work_start"] is None and days[d]["gym"] == 0 for d in dates)


def test_flexible_week_batches_on_prep_days(profile):
    with profile.app_context():
        execute("UPDATE settings SET schedule_mode = 'flexible', prep_days = 2 WHERE id = 1")
        plans.generate_week(MON)
        meals = plans.meals_between(WED, SUN)
        assert any(m["kind"] == "leftover" for m in meals)


def test_overrides_win_over_schedule(profile):
    with profile.app_context():
        plans.set_override(WED, effort="full", gym=1)
        day = plans.build_days([WED])[WED]
        assert day["effort"] == "full" and day["gym"] == 1 and day["prep"]
        plans.set_override(WED, effort=None, gym=None)
        assert not query("SELECT 1 FROM day_overrides")


def test_gym_today_raises_target_and_replans_rest_of_day(profile, client):
    profile.config["NOW"] = "13:00"
    client.post("/plan/generate")
    with profile.app_context():
        before = query("SELECT kcal_target FROM plan_days WHERE date = ?", (WED.isoformat(),), one=True)["kcal_target"]
        early = {m["id"] for m in plans.meals_between(WED, WED) if m["slot"] in ("breakfast", "lunch")}
        thursday = {m["id"] for m in plans.meals_between(WED + timedelta(days=1), WED + timedelta(days=1))}
    client.post("/today/gym")
    with profile.app_context():
        after = query("SELECT kcal_target FROM plan_days WHERE date = ?", (WED.isoformat(),), one=True)["kcal_target"]
        # Wednesday is already a gym day in the default schedule, so the target stays the gym value
        assert after >= before
        assert plans.override(WED)["gym"] == 1
        now_ids = {m["id"] for m in plans.meals_between(WED, WED)}
        assert early <= now_ids   # meals already past stay put
        assert thursday == {m["id"] for m in plans.meals_between(WED + timedelta(days=1), WED + timedelta(days=1))}


def test_free_today_makes_a_prep_day(profile, client):
    client.post("/plan/generate")
    resp = client.post("/today/free", follow_redirects=True)
    assert b"Prep day" in resp.data
    with profile.app_context():
        assert plans.override(WED)["effort"] == "full"
    client.post("/today/free")
    with profile.app_context():
        assert not plans.override(WED)


def test_apply_description_only_takes_valid_values(app):
    with app.app_context():
        s = store.settings()
        sched = [dict(r) for r in query("SELECT * FROM schedule_days ORDER BY weekday")]
    data = {"age": 23, "sex": "male", "weight_kg": 85, "goal_weight_kg": 78, "pace": "steady",
            "schedule_mode": "flexible", "diet": "carnivore", "avoid": ["fish", "aliens"],
            "flavors": ["garlicky", "spicy"], "appliances": ["microwave", "stove"], "gym_days": [1, 3, 9],
            "work_days": [0, 1, 2], "work_start": "10:00", "work_end": "25:00", "spice_tolerance": 99}
    s2, sched2 = apply_description(data, s, sched)
    assert s2["age"] == 23 and s2["schedule_mode"] == "flexible" and s2["pace_kg_week"] == 0.5
    assert s2["diet"] == s["diet"]                      # unknown diet ignored
    assert s2["avoid"] == "fish" and s2["appliances"] == "stove,microwave"
    assert s2["spice_tolerance"] == 5
    assert [d["gym"] for d in sched2] == [0, 1, 0, 1, 0, 0, 0]
    assert sched2[0]["work_start"] == "10:00" and sched2[0]["work_end"] == "18:00"   # bad time ignored
    assert sched2[4]["work_start"] is None


def test_describe_route_prefills_without_saving(app, client):
    class Fake:
        model = "fake"

        def complete(self, prompt, images=(), model=None):
            assert "hate fish" in prompt
            return json.dumps({"age": 23, "sex": "male", "avoid": ["fish"], "schedule_mode": "flexible"})
    app.config["LLM_PROVIDER"] = Fake()
    resp = client.post("/setup/describe", data={"about_me": "23, male, shifts change, hate fish"})
    html = resp.data.decode()
    assert "nothing is saved yet" in html and 'value="23"' in html
    with app.app_context():
        assert store.settings()["age"] is None


def test_wizard_saves_flexible_and_kitchen(app, client):
    from tests.test_preferences import wizard_form
    data = wizard_form(schedule_mode="flexible", prep_days="3", app_microwave="on", app_stove="on")
    client.post("/setup/", data=data)
    with app.app_context():
        s = store.settings()
        assert s["schedule_mode"] == "flexible" and s["prep_days"] == 3
        assert s["appliances"] == "stove,microwave"


def test_edit_day_sets_work_and_replans(profile, client):
    client.post("/plan/generate")
    thu = WED + timedelta(days=1)
    resp = client.post(f"/plan/day/{thu.isoformat()}", data={
        "work_mode": "work", "work_start": "11:00", "work_end": "20:00", "commute_min": "30",
        "gym": "yes", "away": "usual", "effort": "low", "note": "late shift"}, follow_redirects=True)
    assert b"re-planned" in resp.data and b"late shift" in resp.data
    with profile.app_context():
        day = plans.build_days([thu])[thu]
        assert day["work_start"] == "11:00" and day["gym"] == 1 and day["note"] == "late shift"
        meals = plans.meals_between(thu, thu)
        assert {"breakfast", "lunch", "dinner"} <= {m["slot"] for m in meals}
        dinner = next(m for m in meals if m["slot"] == "dinner")
        assert dinner["recipe"] is None or dinner["recipe"]["total_min"] <= 30 or dinner["kind"] == "leftover"


def test_edit_day_rejects_bad_hours(profile, client):
    resp = client.post(f"/plan/day/{WED.isoformat()}", data={"work_mode": "work", "work_start": "", "work_end": ""},
                       follow_redirects=True)
    assert b"start and end time" in resp.data
    assert client.get(f"/plan/day/{WED.isoformat()}").status_code == 200


def test_day_off_clears_usual_work(profile, client):
    client.post(f"/plan/day/{WED.isoformat()}", data={"work_mode": "off", "gym": "usual", "away": "usual", "effort": "usual"})
    with profile.app_context():
        assert plans.build_days([WED])[WED]["work_start"] is None


def test_editing_a_day_replans_the_rest_of_the_week(profile, client):
    client.post("/plan/generate")
    thu, sat = WED + timedelta(days=1), WED + timedelta(days=3)
    with profile.app_context():
        execute("UPDATE plan_meals SET replace_flag = 1 WHERE date = ?", (sat.isoformat(),))
        before_kcal = query("SELECT kcal_target FROM plan_days WHERE date = ?", (thu.isoformat(),), one=True)["kcal_target"]
    client.post(f"/plan/day/{thu.isoformat()}", data={
        "work_mode": "work", "work_kind": "physical", "work_start": "07:00", "work_end": "18:00", "commute_min": "20",
        "gym": "usual", "away": "usual", "effort": "usual"})
    with profile.app_context():
        after_kcal = query("SELECT kcal_target FROM plan_days WHERE date = ?", (thu.isoformat(),), one=True)["kcal_target"]
        assert after_kcal > before_kcal + 300                  # physical 11-hour shift: real food
        assert not any(m["replace_flag"] for m in plans.meals_between(sat, sat))   # later days re-planned too
        thursday_food = sum(m["kcal"] for m in plans.meals_between(thu, thu))
        assert thursday_food >= after_kcal * 0.85


def test_got_work_tick_on_the_week_page(profile, client):
    client.post("/plan/generate")
    fri = WED + timedelta(days=2)
    client.post(f"/plan/day/{fri.isoformat()}/work", data={})          # unticked: day off
    with profile.app_context():
        assert plans.build_days([fri])[fri]["work_start"] is None
    client.post(f"/plan/day/{fri.isoformat()}/work",
                data={"work": "1", "work_start": "13:00", "work_end": "22:00", "work_kind": "standing"})
    with profile.app_context():
        day = plans.build_days([fri])[fri]
        assert (day["work_start"], day["work_end"], day["work_job"]) == ("13:00", "22:00", "standing")
    bad = client.post(f"/plan/day/{fri.isoformat()}/work", data={"work": "1", "work_start": "", "work_end": ""})
    assert bad.status_code == 302 and f"/plan/day/{fri.isoformat()}" in bad.headers["Location"]


def test_activities_any_kind_one_day_or_weekly(profile, client):
    client.post("/plan/generate")
    thu = WED + timedelta(days=1)
    client.post(f"/plan/day/{thu.isoformat()}/work", data={})          # no usual work that day
    client.post(f"/plan/day/{thu.isoformat()}/activity",
                data={"kind": "school", "label": "Calculus", "start": "09:00", "end": "12:00", "intensity": "desk"})
    client.post(f"/plan/day/{thu.isoformat()}/activity",
                data={"kind": "parttime", "start": "17:00", "end": "22:00", "intensity": "standing", "weekly": "1"})
    with profile.app_context():
        day = plans.build_days([thu])[thu]
        labels = [(b["label"], b["weekly"]) for b in day["blocks"]]
        assert labels == [("Calculus", False), ("Part-time", True)]
        from mealplanner.schedule import slot_limits
        lim = slot_limits(day)
        assert lim["dinner"]["away"] and not lim["lunch"]["away"]       # 19:00 dinner falls in the shift
        nxt = thu + timedelta(days=7)
        assert [b["label"] for b in plans.build_days([nxt])[nxt]["blocks"]] == ["Work", "Part-time"]
        weekly_id = query("SELECT id FROM activities WHERE weekday IS NOT NULL", one=True)["id"]
    page = client.get("/plan/").get_data(as_text=True)
    assert "Calculus" in page and "+ Add" in page
    client.post(f"/plan/activity/{weekly_id}/remove", data={"date": thu.isoformat()})            # skip one day
    with profile.app_context():
        assert [b["label"] for b in plans.build_days([thu])[thu]["blocks"]] == ["Calculus"]
        assert "Part-time" in [b["label"] for b in plans.build_days([nxt])[nxt]["blocks"]]
    client.post(f"/plan/activity/{weekly_id}/remove", data={"date": thu.isoformat(), "scope": "all"})
    with profile.app_context():
        assert "Part-time" not in [b["label"] for b in plans.build_days([nxt])[nxt]["blocks"]]


def test_gym_activity_makes_it_a_gym_day(profile, client):
    sat = WED + timedelta(days=3)
    client.post(f"/plan/day/{sat.isoformat()}/activity", data={"kind": "gym", "start": "10:00", "end": "11:30"})
    with profile.app_context():
        assert plans.build_days([sat])[sat]["gym"] == 1
