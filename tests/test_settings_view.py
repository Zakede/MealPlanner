from mealplanner import store


def form(**overrides):
    data = {
        "units": "metric", "height_cm": "190", "weight_kg": "85", "goal_weight_kg": "78",
        "age": "25", "sex": "male", "job": "desk", "training_days": "3", "training_intensity": "moderate",
        "pace_kg_week": "0.5", "diet": "any",
        "weekly_budget_yen": "10000", "eat_out_slots": "1", "eat_out_budget_yen": "1200",
        "eat_out_kcal": "800", "snack_kcal": "200", "spice_tolerance": "3",
        "allergies": "", "dislikes": "", "flavor_likes": "", "cuisines_liked": "", "cuisines_tired": "",
    }
    data.update(overrides)
    return data


def test_defaults_need_age_and_sex(app, client):
    with app.app_context():
        s = store.settings()
        assert s["height_cm"] == 190 and s["weight_kg"] == 85 and s["goal_weight_kg"] == 78
        assert store.targets(s) is None
    resp = client.get("/")
    assert resp.status_code == 302 and "/setup/" in resp.headers["Location"]


def test_save_settings_computes_targets(app, client):
    resp = client.post("/settings/", data=form(), follow_redirects=True)
    assert resp.status_code == 200
    # BMR 1917.5 x (1.2 desk + 3 x 0.035 training) - 550 deficit
    assert b"1950" in resp.data
    with app.app_context():
        assert store.targets().kcal == 1950


def test_invalid_values_rejected(app, client):
    resp = client.post("/settings/", data=form(height_cm="abc", age="5"), follow_redirects=True)
    assert b"must be a number" in resp.data
    with app.app_context():
        assert store.settings()["age"] is None


def test_imperial_input_stored_as_metric(app, client):
    client.post("/settings/", data=form(units="imperial", height_cm="74.8", weight_kg="187.4",
                                        goal_weight_kg="172", pace_kg_week="1.1"))
    with app.app_context():
        s = store.settings()
        assert abs(s["height_cm"] - 190) < 0.5
        assert abs(s["weight_kg"] - 85) < 0.1


def test_theme_change_applies_without_replanning(profile, client):
    from datetime import date
    from mealplanner import plans
    with profile.app_context():
        plans.generate_week(date(2026, 10, 5))
        ids = {m["id"] for m in plans.meals_between(date(2026, 10, 7), date(2026, 10, 11))}
    client.post("/settings/", data=form(theme="apothecary", mode="dark"))
    page = client.get("/").data
    assert b'data-palette="apothecary"' in page and b'data-mode="dark"' in page
    with profile.app_context():
        assert {m["id"] for m in plans.meals_between(date(2026, 10, 7), date(2026, 10, 11))} == ids


def test_home_shows_widgets_and_day_list(profile, client):
    client.post("/plan/generate")
    page = client.get("/").data
    assert b'class="tiles"' in page and b'class="day-list"' in page


def test_more_page(client):
    assert client.get("/more").status_code == 200
