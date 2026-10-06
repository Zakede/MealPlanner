from datetime import date

import pytest

from mealplanner import plans, store
from mealplanner.db import query
from mealplanner.diet import allowed
from mealplanner.nutrition import MAX_DEFICIT, compute_targets
from mealplanner.pricing import factor, options_json

MON = date(2026, 10, 5)


def test_deficit_mode_and_macros():
    t = compute_targets(85, 190, 25, "male", 1.305, 0.5, 78, deficit_kcal=300)
    assert t.tdee - t.kcal == pytest.approx(300, abs=10)
    capped = compute_targets(85, 190, 25, "male", 1.305, 0.5, 78, deficit_kcal=1000)
    assert capped.tdee - capped.kcal == pytest.approx(MAX_DEFICIT, abs=10) and capped.pace_capped
    high = compute_targets(85, 190, 25, "male", 1.305, 0.5, 78, protein_per_kg=2.2, fat_share=0.3)
    assert high.protein_g == 187 and high.fat_g == round(high.kcal * 0.3 / 9)


def test_deficit_setting_changes_targets(profile, client):
    from tests.test_settings_view import form
    client.post("/settings/", data=form(goal_mode="deficit", deficit_kcal="250", protein_per_kg="2.0"))
    with profile.app_context():
        t = store.targets()
        assert t.tdee - t.kcal == pytest.approx(250, abs=10) and t.protein_g == 170


def test_new_avoid_options(app):
    with app.app_context():
        recipes = {r["name"]: r for r in store.recipes()}
    assert not allowed(recipes["Chicken teriyaki rice bowl"], "any", ["chicken"])
    assert not allowed(recipes["Chicken tomato pasta"], "any", ["gluten"])
    assert not allowed(recipes["Peanut butter banana toast"], "any", ["nuts"])
    assert not allowed(recipes["Beef & broccoli rice"], "any", ["allium"])     # garlic
    assert allowed(recipes["Greek yogurt berry bowl"], "any", ["chicken", "gluten", "mushroom"])


def test_country_switch_data():
    data = options_json()
    assert [k for k, _ in data["JP"]["shops"]][0] == "gyomu"
    assert data["US"]["symbol"] == "$" and any("Costco" in label for _, label in data["US"]["shops"])
    assert factor({"country": "US", "area": "big_city", "shop": "discount"}) == pytest.approx(0.0067 * 1.45 * 1.05 * 0.85)


def test_lock_flow(app, client):
    assert client.get("/more").status_code == 200          # open while no password is set
    resp = client.post("/lock", data={"password": "short", "again": "short"}, follow_redirects=True)
    assert b"at least 6" in resp.data
    client.post("/lock", data={"password": "wisteria1", "again": "wisteria1"})
    with app.app_context():
        assert store.settings()["password_hash"].startswith(("scrypt:", "pbkdf2:"))
    assert client.get("/more").status_code == 200          # the browser that set it stays in
    client.post("/logout")
    resp = client.get("/more")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]
    assert client.get("/static/style.css").status_code == 200
    bad = client.post("/login", data={"password": "nope"}, follow_redirects=True)
    assert b"Wrong password" in bad.data
    ok = client.post("/login?next=/more", data={"password": "wisteria1"})
    assert ok.headers["Location"].endswith("/more")
    evil = client.post("/login?next=//evil.example", data={"password": "wisteria1"})
    assert "evil" not in evil.headers["Location"]
    client.post("/lock", data={"off": "1"})
    client.post("/logout")
    assert client.get("/more").status_code == 200


def test_shopping_preview_from_draft(profile, client):
    client.post("/plan/generate")
    page = client.get("/plan/shopping").data.decode()
    assert "From your draft plan" in page and "Approve week" in page
    with profile.app_context():
        assert query("SELECT COUNT(*) c FROM shopping_list", one=True)["c"] == 0
        assert plans.shopping_preview(MON)


def test_shop_in_bottom_bar(profile, client):
    client.post("/plan/generate")
    assert "買物" in client.get("/").data.decode()
