from datetime import timedelta

from flask import Blueprint, render_template

from .. import plans, planner, store, today
from ..db import query
from ..nutrition import day_targets
from ..schedule import minutes

bp = Blueprint("main", __name__)

DONE = ("cooked", "eaten", "skipped", "eaten_out")


def today_targets(s, targets, on):
    row = query("SELECT * FROM plan_days WHERE date = ?", (on.isoformat(),), one=True)
    if row:
        return row["kcal_target"], row["protein_target"]
    sched = {r["weekday"]: dict(r) for r in query("SELECT * FROM schedule_days")}
    gym_days = sum(1 for d in sched.values() if d["gym"])
    return day_targets(targets, sched[on.weekday()]["gym"], gym_days, s["sex"])


def reminders(on, recipes_by_id):
    out = []
    tomorrow = plans.meals_between(on + timedelta(days=1), on + timedelta(days=1))
    for r in planner.thaw_reminders(tomorrow, recipes_by_id, on):
        out.append(f"Tonight {r['at']}: thaw for {r['recipe']['name']}")
    for item in store.pantry_items(on):
        if item["days_left"] is not None and 0 <= item["days_left"] <= 1:
            out.append(f"{item['name']} expires {'today' if item['days_left'] == 0 else 'tomorrow'}")
    for lo in query("SELECT * FROM leftovers WHERE portions > 0 AND safe_until <= ?",
                    ((on + timedelta(days=1)).isoformat(),)):
        out.append(f"Eat the leftover {lo['title']} by {lo['safe_until']}")
    return out


@bp.route("/")
def home():
    s = store.settings()
    targets = store.targets(s)
    if targets is None:
        return render_template("home.html", needs_profile=True)

    on = today()
    recipes_by_id = {r["id"]: r for r in store.recipes()}
    meals = plans.meals_between(on, on)
    kcal_target, protein_target = today_targets(s, targets, on)
    eaten = [m for m in meals if m["status"] in ("cooked", "eaten", "eaten_out")]
    kcal_eaten = round(sum(m["kcal"] for m in eaten))
    protein_eaten = round(sum(m["protein"] for m in eaten))

    now = plans.now_minutes()
    upcoming = [m for m in meals if m["status"] not in DONE and m["kind"] != "empty"]
    next_meal = next((m for m in upcoming if m["eat_time"] and minutes(m["eat_time"]) >= now - 60), None) \
        or (upcoming[0] if upcoming else None)
    start_at = planner.start_cooking_at(next_meal, recipes_by_id.get(next_meal["recipe_id"])) \
        if next_meal and next_meal["kind"] == "cook" else None

    first, _ = plans.current_week(on)
    return render_template(
        "home.html",
        needs_profile=False,
        on=on,
        meals=meals,
        next_meal=next_meal,
        start_at=start_at,
        kcal_target=kcal_target,
        protein_target=protein_target,
        kcal_eaten=kcal_eaten,
        protein_eaten=protein_eaten,
        budget=plans.week_budget(first),
        reminders=reminders(on, recipes_by_id),
        has_plan=plans.week_has_plan(first),
    )


@bp.route("/more")
def more():
    return render_template("more.html")
