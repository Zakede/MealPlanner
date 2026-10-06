from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import plans, planner, store, today
from ..db import query
from ..nutrition import day_targets
from .. import tracking


def track_water(on):
    row = query("SELECT ml FROM water_log WHERE date = ?", (on.isoformat(),), one=True)
    return row["ml"] if row else 0

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


def try_something_new(s, on):
    """One food worth trying today (rotates daily; ?idea=n shows the next one)."""
    from .. import diet, discoveries
    prefs = store.recipe_prefs()
    avoid = store.split_list(s.get("avoid"))
    allergies = set(store.split_list(s.get("allergies")))
    recipes = []
    for r in store.recipes():
        r = dict(r, pref=prefs.get(r["id"]))
        tags = {a for i in r["ingredients"] for a in store.split_list(i.get("allergens"))}
        r["fits"] = diet.allowed(r, s.get("diet") or "any", avoid) and not (allergies & tags)
        recipes.append(r)
    options = discoveries.candidates(recipes, discoveries.recent_foods(query, on), on)
    if not options:
        return None
    try:
        n = int(request.args.get("idea", 0))
    except ValueError:
        n = 0
    pick = options[n % len(options)]
    pick["next"] = (n + 1) % len(options)
    pick["count"] = len(options)
    return pick


@bp.route("/")
def home():
    s = store.settings()
    targets = store.targets(s)
    if targets is None or not s.get("setup_done"):
        return redirect(url_for("setup.start"))

    on = today()
    recipes_by_id = {r["id"]: r for r in store.recipes()}
    meals = plans.meals_between(on, on)
    kcal_target, protein_target = today_targets(s, targets, on)
    eaten = [m for m in meals if m["status"] in ("cooked", "eaten")]
    extras = query("SELECT * FROM food_log WHERE date = ? ORDER BY id", (on.isoformat(),))
    out = query("SELECT * FROM eating_out_log WHERE date = ?", (on.isoformat(),))
    kcal_eaten = round(sum(m["kcal"] for m in eaten) + sum(e["kcal"] for e in extras) + sum(e["kcal"] for e in out))
    protein_eaten = round(sum(m["protein"] for m in eaten) + sum(e["protein"] for e in extras)
                          + sum(e["protein"] for e in out))

    # the next meal is the first one not eaten yet; meal times are only a suggestion
    upcoming = [m for m in meals if m["status"] not in DONE and m["kind"] != "empty"]
    next_meal = upcoming[0] if upcoming else None
    start_at = planner.start_cooking_at(next_meal, recipes_by_id.get(next_meal["recipe_id"])) \
        if next_meal and next_meal["kind"] == "cook" else None

    first, _ = plans.current_week(on)
    return render_template(
        "home.html",
        idea=try_something_new(s, on),
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
        today_override=plans.override(on),
        extras=[dict(e) for e in extras],
        week=week_strip(first, on),
        shop=shop_summary(first),
        water_ml=track_water(on),
        water_target=tracking.water_target_ml(s["weight_kg"]),
        last_weigh=query("SELECT * FROM weight_log ORDER BY date DESC LIMIT 1", one=True),
        day=plans.build_days([on])[on],
    )


def week_strip(first, on):
    """One small column per day: how full the day is against its target."""
    days = []
    targets = {r["date"]: r["kcal_target"] for r in query("SELECT * FROM plan_days WHERE date BETWEEN ? AND ?",
                                                          (first.isoformat(), (first + timedelta(days=6)).isoformat()))}
    meals = plans.meals_between(first, first + timedelta(days=6))
    logged = {}
    for r in query("SELECT date, SUM(kcal) k FROM food_log WHERE date BETWEEN ? AND ? GROUP BY date",
                   (first.isoformat(), (first + timedelta(days=6)).isoformat())):
        logged[r["date"]] = r["k"]
    for i in range(7):
        d = first + timedelta(days=i)
        ms = [m for m in meals if m["date"] == d and m["status"] != "skipped"]
        planned = sum(m["kcal"] for m in ms) + (logged.get(d.isoformat()) or 0)
        target = targets.get(d.isoformat())
        days.append({"date": d, "today": d == on, "past": d < on, "has": bool(ms),
                     "pct": min(100, round(planned / target * 100)) if target else 0,
                     "over": bool(target and planned > target * 1.05)})
    return days


def shop_summary(first):
    items = plans.shopping_list(first)
    preview = False
    if not items:
        items = plans.shopping_preview(first)
        preview = True
    left = [i for i in items if not i["checked"]]
    return {"count": len(left), "cost": sum(i["est_cost"] for i in left), "preview": preview}


@bp.route("/today/<what>", methods=["POST"])
def today_toggle(what):
    """Quick switches for days that don't follow the usual pattern."""
    on = today()
    current = plans.override(on)
    if what == "free":
        turning_on = current.get("effort") != "full"
        plans.set_override(on, effort="full" if turning_on else None)
        first, _ = plans.current_week(on)
        if plans.week_has_plan(first):
            plans.generate_week(first)
        flash("Prep day: today gets a bigger cook and the leftovers cover the next few days." if turning_on
              else "Back to a normal day.", "ok")
    elif what == "gym":
        turning_on = not current.get("gym")
        plans.set_override(on, gym=1 if turning_on else None)
        plans.replan_rest_of_day(on)
        flash("Gym day: a bit more food and protein for the rest of today." if turning_on
              else "Gym day removed.", "ok")
    elif what == "away":
        turning_on = not current.get("away")
        plans.set_override(on, away=1 if turning_on else None)
        plans.replan_rest_of_day(on)
        flash("Out today: lunch and dinner are things you can take or buy." if turning_on
              else "Home again.", "ok")
    return redirect(request.referrer or url_for("main.home"))


@bp.route("/more")
def more():
    return render_template("more.html")


@bp.route("/api/nudges")
def api_nudges():
    """In-app notifications for right now (the page polls this)."""
    from flask import jsonify, render_template_string
    from .. import nudges
    if store.targets() is None:
        return jsonify({"nudges": []})
    items = nudges.build(today(), plans.now_minutes())
    draw = '{% from "_icons.html" import icon %}{{ icon(name) }}'
    for n in items:
        n["svg"] = render_template_string(draw, name=n["icon"])
    return jsonify({"nudges": items, "day": today().isoformat()})
