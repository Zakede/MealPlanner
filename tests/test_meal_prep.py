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


def test_late_boxes_go_in_the_freezer_or_stop_without_one(profile):
    _, _, meals = _setup(profile)
    late = [m for m in meals if "freeze this box" in (m["note"] or "")]
    assert late                                             # fridge life is ~3 days, the week is longer
    with profile.app_context():
        execute("UPDATE settings SET appliances = 'stove,microwave,rice_cooker' WHERE id = 1")
    _, _, meals = _setup(profile)
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
