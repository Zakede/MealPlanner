"""Little in-app notifications: what to do now, worked out from the plan, pantry and logs.

Each nudge has a stable id for the day, so the page can show it once and remember it was dismissed.
"""
from datetime import timedelta

from . import planner, plans, store
from .db import query
from .schedule import hhmm, minutes

DONE = ("cooked", "eaten", "skipped", "eaten_out")
SOON_MIN = 45          # a meal this close gets a heads-up
WATER_DAY = (8 * 60, 22 * 60)


def _n(nid, icon, title, body="", url=None, urgent=False):
    return {"id": nid, "icon": icon, "title": title, "body": body, "url": url, "urgent": urgent}


def build(on, now_min):
    """Nudges for this moment. on: today's date, now_min: minutes since midnight."""
    from flask import url_for
    s = store.settings()
    out = []
    recipes = {r["id"]: r for r in store.recipes()}
    meals = plans.meals_between(on, on)

    # the next meal: time to start cooking, or time to eat
    for m in meals:
        if m["status"] in DONE or not m.get("eat_time"):
            continue
        eat = minutes(m["eat_time"])
        recipe = recipes.get(m["recipe_id"])
        start = planner.start_cooking_at(m, recipe) if m["kind"] == "cook" else None
        start_min = minutes(start) if start else eat
        if start_min - SOON_MIN <= now_min <= eat + 30:
            if m["kind"] == "cook" and now_min < eat:
                title = f"Start cooking at {start}" if now_min < start_min else f"Time to cook: {m['title']}"
                body = f"{m['slot'].capitalize()} at {m['eat_time']} · {round(m['kcal'])} kcal"
            else:
                title = f"{m['slot'].capitalize()} at {m['eat_time']}"
                body = f"{m['title']} · {round(m['kcal'])} kcal"
            out.append(_n(f"meal-{m['id']}", "bowl", title, body,
                          url_for("cook.cook", meal_id=m["id"]) if m["recipe_id"] else url_for("main.home"),
                          urgent=now_min >= start_min))
            break

    # thaw tonight for tomorrow
    if now_min >= 17 * 60:
        tomorrow = plans.meals_between(on + timedelta(days=1), on + timedelta(days=1))
        for r in planner.thaw_reminders(tomorrow, recipes, on):
            out.append(_n(f"thaw-{r['recipe']['id']}", "snow", f"Thaw tonight ({r['at']})",
                          f"For tomorrow's {r['recipe']['name']}", url_for("plan.week")))

    # food about to go off
    for item in store.pantry_items(on):
        if item["days_left"] is not None and 0 <= item["days_left"] <= 1:
            when = "today" if item["days_left"] == 0 else "tomorrow"
            out.append(_n(f"exp-{item['id']}", "pantry", f"{item['name']} expires {when}",
                          "Cook now finds a meal that uses it", url_for("track.cook_now")))
    for lo in query("SELECT * FROM leftovers WHERE portions > 0 AND safe_until <= ?",
                    ((on + timedelta(days=1)).isoformat(),)):
        out.append(_n(f"lo-{lo['id']}", "bowl", f"Eat the {lo['title']} leftovers",
                      f"Good until {lo['safe_until']}", url_for("cook.leftovers")))

    # water: behind where you'd be by now
    from .tracking import water_target_ml
    row = query("SELECT ml FROM water_log WHERE date = ?", (on.isoformat(),), one=True)
    drank = row["ml"] if row else 0
    target = water_target_ml(s.get("weight_kg") or 70)
    start, end = WATER_DAY
    if start < now_min < end:
        expected = target * (now_min - start) / (end - start)
        if drank < expected - 500:
            out.append(_n(f"water-{now_min // 120}", "drop", "Drink some water",
                          f"{drank / 1000:.1f} of {target / 1000:.1f} L so far", url_for("main.home")))

    # weigh-in in the morning
    if 6 * 60 <= now_min <= 11 * 60 and not query("SELECT 1 FROM weight_log WHERE date = ?", (on.isoformat(),), one=True):
        out.append(_n("weigh", "scale", "Morning weigh-in", "Before breakfast is most accurate", url_for("track.progress")))

    # plans waiting for you
    first, _ = plans.current_week(on)
    nxt = first + timedelta(days=7)
    if on.weekday() >= 4 and not plans.week_has_plan(nxt):
        out.append(_n(f"plan-{nxt.isoformat()}", "plan", "Plan next week", "It takes one tap",
                      url_for("plan.week", week="next")))
    for week, label in ((first, "This week"), (nxt, "Next week")):
        if query("SELECT 1 FROM plan_meals WHERE status = 'draft' AND date BETWEEN ? AND ? LIMIT 1",
                 (week.isoformat(), (week + timedelta(days=6)).isoformat())):
            out.append(_n(f"draft-{week.isoformat()}", "plan", f"{label} is waiting for approval",
                          "Approve it to get the shopping list",
                          url_for("plan.week", week="next" if week == nxt else None)))

    # yesterday's dinner, unrated
    y = on - timedelta(days=1)
    unrated = query("""SELECT pm.* FROM plan_meals pm WHERE pm.date = ? AND pm.status IN ('cooked', 'eaten')
                       AND pm.recipe_id IS NOT NULL AND pm.kind = 'cook'
                       AND NOT EXISTS (SELECT 1 FROM ratings r WHERE r.recipe_id = pm.recipe_id AND r.rated_on >= ?)
                       LIMIT 1""", (y.isoformat(), y.isoformat()), one=True)
    if unrated:
        out.append(_n(f"rate-{unrated['id']}", "star", f"How was {unrated['title']}?", "Rate it so plans get better",
                      url_for("cook.rate", meal_id=unrated["id"])))
    return out
