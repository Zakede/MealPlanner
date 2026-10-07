from datetime import date

from mealplanner import plans, store
from mealplanner.db import execute, query


def _setup(app, covers="lunch_dinner", today="2026-10-11"):
    app.config["TODAY"] = today          # a Sunday
    with app.app_context():
        execute("UPDATE settings SET prep_weekdays = '6', prep_covers = ? WHERE id = 1", (covers,))
        first, last = plans.current_week()
        plans.generate_week(first)
        meals = [dict(r) for r in query("SELECT * FROM plan_meals WHERE date BETWEEN ? AND ? ORDER BY date",
                                        (first.isoformat(), last.isoformat()))]
    return first, last, meals


def test_week_starts_on_the_prep_day(profile):
    first, last, _ = _setup(profile)
    assert first == date(2026, 10, 11) and first.weekday() == 6 and last == date(2026, 10, 17)


def test_prep_day_boxes_up_lunches_and_dinners_for_the_week(profile):
    first, _, meals = _setup(profile)
    prep = [m for m in meals if m["date"] == first.isoformat() and "Meal prep" in (m["note"] or "")]
    assert prep, "the prep day should batch cook"
    boxes = [m for m in meals if "From the Sun prep" in (m["note"] or "")]
    assert len({m["slot"] for m in boxes}) == 2              # both lunches and dinners
    assert len(boxes) >= 6
    assert sum(m["cook_portions"] for m in prep) >= len(boxes) + len(prep) - 0.01


def test_lunch_only_prep_keeps_dinners_fresh(profile):
    _, _, meals = _setup(profile, covers="lunch")
    boxes = [m for m in meals if "From the Sun prep" in (m["note"] or "")]
    assert boxes and all(m["slot"] == "lunch" for m in boxes)


def test_two_prep_dishes_and_late_boxes_go_in_the_freezer(profile):
    # "lunches" prep: the Sunday lunch cook boxes Mon-Wed lunches, the Sunday dinner cook is a second dish
    # for Thu-Sat lunches, which are past fridge life, so those boxes are frozen
    first, _, meals = _setup(profile, covers="lunch")
    cooks = {m["title"] for m in meals if m["date"] == first.isoformat() and "Meal prep" in (m["note"] or "")}
    assert len(cooks) == 2
    boxes = [m for m in meals if "From the Sun prep" in (m["note"] or "")]
    assert all(m["slot"] == "lunch" for m in boxes) and len({m["title"] for m in boxes}) == 2
    assert max(sum(1 for b in boxes if b["title"] == t) for t in cooks) <= 3
    late = [m for m in meals if "freeze this box" in (m["note"] or "")]
    assert late                                             # fridge life is ~3 days, the week is longer
    with profile.app_context():
        execute("UPDATE settings SET appliances = 'stove,microwave,rice_cooker' WHERE id = 1")
    _, _, meals = _setup(profile, covers="lunch")
    assert not [m for m in meals if "freeze this box" in (m["note"] or "")]


def test_setup_and_settings_save_the_prep_picker(profile, client):
    from werkzeug.datastructures import MultiDict
    from mealplanner.views.setup import prep_from_form
    v = prep_from_form(MultiDict({"prep_6": "on", "prep_2": "on", "prep_covers": "lunch_dinner"}))
    assert v == {"prep_weekdays": "2,6", "prep_covers": "lunch_dinner"}
    with profile.app_context():
        execute("UPDATE settings SET prep_weekdays = '2' WHERE id = 1")
        assert store.week_start() == 2
    page = client.get("/settings/").data.decode()
    assert "Meal prep day" in page and 'name="prep_2" id="prep2" checked' in page


def test_cooking_prep_freezes_the_late_boxes(profile, client):
    first, _, meals = _setup(profile, covers="lunch")
    dinner_prep = next(m for m in meals if m["date"] == first.isoformat() and m["slot"] == "dinner"
                       and "Meal prep" in (m["note"] or ""))
    client.post(f"/cook/{dinner_prep['id']}/done")
    with profile.app_context():
        rows = query("SELECT location, portions, safe_until FROM leftovers ORDER BY location")
    assert {r["location"] for r in rows} == {"freezer"} or "freezer" in {r["location"] for r in rows}
    frozen = [r for r in rows if r["location"] == "freezer"]
    assert frozen and frozen[0]["safe_until"] > "2026-10-30"


def test_normal_budget_never_leaves_a_day_empty(profile):
    profile.config["TODAY"] = "2026-10-11"
    with profile.app_context():
        execute("UPDATE settings SET prep_weekdays = '6', prep_covers = 'lunch', eat_out_slots = 2,"
                " weekly_budget_yen = 8000 WHERE id = 1")
        first, last = plans.current_week()
        plans.generate_week(first)
        assert not query("SELECT 1 FROM plan_meals WHERE kind = 'empty'")


def test_expired_leftovers_clear_themselves(profile, client):
    with profile.app_context():
        execute("INSERT INTO leftovers (title, portions, kcal, protein, carbs, fat, cooked_on, safe_until)"
                " VALUES ('Old curry', 1, 500, 30, 50, 10, '2026-09-30', '2026-10-03')")
        execute("INSERT INTO leftovers (title, portions, kcal, protein, carbs, fat, cooked_on, safe_until)"
                " VALUES ('Yesterday soup', 1, 300, 20, 30, 5, '2026-10-04', '2026-10-06')")
    page = client.get("/").data.decode()
    assert "Toss the leftover Yesterday soup" in page and "Old curry" not in page
