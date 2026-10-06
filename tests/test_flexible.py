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
