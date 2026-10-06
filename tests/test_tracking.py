import json
from datetime import date, timedelta

import pytest

from mealplanner import store, tracking
from mealplanner.db import execute, query

D = date(2026, 10, 7)


def test_water_target():
    assert tracking.water_target_ml(85) == 3000      # 2975 ml rounds to 12 glasses
    assert tracking.water_target_ml(40) == 1500
    assert tracking.water_target_ml(10) == 1000      # never below 4 glasses


def test_moving_average_and_weekly_change():
    entries = [(D - timedelta(days=13 - i), 86 - i * 0.1) for i in range(14)]
    avg = tracking.moving_average(entries)
    assert avg[0][1] == 86
    assert avg[-1][1] == pytest.approx(sum(kg for _, kg in entries[-7:]) / 7, abs=0.01)
    assert tracking.weekly_change(entries) == pytest.approx(-0.7, abs=0.05)
    assert tracking.weekly_change(entries[:2]) is None


def test_chart_points_fit_the_box():
    raw, trend, lo, hi = tracking.chart_points([(D, 85.0), (D + timedelta(days=10), 84.0)])
    xs = [float(p.split(",")[0]) for p in raw.split()]
    ys = [float(p.split(",")[1]) for p in raw.split()]
    assert xs == [10.0, 310.0] and all(10 <= y <= 110 for y in ys)
    assert lo == 83.5 and hi == 85.5
    assert tracking.chart_points([]) == ("", "", None, None)


def test_water_buttons(app, client):
    client.post("/water")
    client.post("/water")
    client.post("/water", data={"change": "minus"})
    with app.app_context():
        assert query("SELECT ml FROM water_log", one=True)["ml"] == 250
    client.post("/water", data={"change": "minus"})
    client.post("/water", data={"change": "minus"})
    with app.app_context():
        assert query("SELECT ml FROM water_log", one=True)["ml"] == 0


def test_weigh_in_updates_targets(profile, client):
    with profile.app_context():
        before = store.targets().kcal
    resp = client.post("/progress", data={"kg": "83.4"}, follow_redirects=True)
    assert b"Logged 83.4 kg" in resp.data
    with profile.app_context():
        assert store.settings()["weight_kg"] == 83.4
        assert store.targets().kcal < before
    assert b"polyline" in client.get("/progress").data
    assert b"Enter your weight" in client.post("/progress", data={"kg": "abc"}, follow_redirects=True).data


def test_cook_now_lists_what_the_pantry_covers(app, client):
    for name, qty in (("Chicken breast", 300), ("Cooked rice", 400), ("Frozen broccoli", 200)):
        client.post("/pantry/new", data={"name": name, "quantity": str(qty), "unit": "g", "location": "fridge",
                                         "expiry": "2026-10-08", "kcal": "100", "protein": "10", "carbs": "10", "fat": "1"})
    page = client.get("/cook-now").data.decode()
    assert "Chicken teriyaki rice bowl" in page     # soy sauce and mirin are small enough to assume
    assert "Oyakodon" not in page                    # needs eggs and onion


def test_backup_leaves_out_the_key(app, client):
    with app.app_context():
        execute("UPDATE settings SET gemini_key = 'secret-key' WHERE id = 1")
    resp = client.get("/backup")
    assert resp.headers["Content-Disposition"].startswith("attachment")
    data = json.loads(resp.data)
    assert "recipes" in data["tables"] and "secret-key" not in resp.data.decode()


def test_reset_needs_confirmation_and_keeps_key(profile, client):
    with profile.app_context():
        execute("UPDATE settings SET gemini_key = 'k1' WHERE id = 1")
    client.post("/plan/generate")
    resp = client.post("/reset", data={"confirm": "nope"}, follow_redirects=True)
    assert b"Nothing was deleted" in resp.data
    with profile.app_context():
        assert query("SELECT COUNT(*) c FROM plan_meals", one=True)["c"] > 0
    resp = client.post("/reset", data={"confirm": "reset", "keep_key": "on"})
    assert "/setup/" in resp.headers["Location"]
    with profile.app_context():
        s = store.settings()
        assert s["age"] is None and s["gemini_key"] == "k1"
        assert query("SELECT COUNT(*) c FROM plan_meals", one=True)["c"] == 0
        assert query("SELECT COUNT(*) c FROM recipes", one=True)["c"] > 30


def test_reset_can_drop_key(profile, client):
    with profile.app_context():
        execute("UPDATE settings SET gemini_key = 'k1' WHERE id = 1")
    client.post("/reset", data={"confirm": "RESET"})
    with profile.app_context():
        assert store.settings()["gemini_key"] == ""
