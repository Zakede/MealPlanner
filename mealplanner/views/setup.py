from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import plans, store
from ..db import get_db
from ..diet import AVOID_OPTIONS, DIETS
from ..nutrition import JOB_LEVELS, TRAINING_LEVELS
from ..schedule import WEEKDAYS

bp = Blueprint("setup", __name__, url_prefix="/setup")

FLAVORS = ["spicy", "garlicky", "cheesy", "sweet-savory", "crunchy", "fresh", "creamy", "comfort", "sour"]
CUISINES = ["japanese", "korean", "chinese", "western", "italian", "mexican", "indian"]
PACES = [(0.25, "Gentle", "about 1 kg a month"), (0.5, "Steady", "about 2 kg a month"),
         (0.75, "Fast", "about 3 kg a month, the safe max")]
EFFORTS = [("none", "No cooking"), ("low", "Quick (15 min)"), ("full", "Happy to cook")]


def _num(form, key, lo, hi, cast=float):
    try:
        value = cast(float(form.get(key, "")))
    except ValueError:
        raise ValueError(f"{key.replace('_', ' ')} is missing")
    if not lo <= value <= hi:
        raise ValueError(f"{key.replace('_', ' ')} should be between {lo} and {hi}")
    return value


def parse(form):
    v = {
        "age": _num(form, "age", 16, 100, int),
        "height_cm": _num(form, "height_cm", 120, 230),
        "weight_kg": _num(form, "weight_kg", 35, 300),
        "goal_weight_kg": _num(form, "goal_weight_kg", 35, 300),
        "pace_kg_week": _num(form, "pace_kg_week", 0, 0.75),
        "training_days": _num(form, "training_days", 0, 7, int),
        "weekly_budget_yen": _num(form, "weekly_budget_yen", 0, 200000, int),
        "eat_out_slots": _num(form, "eat_out_slots", 0, 14, int),
        "eat_out_budget_yen": _num(form, "eat_out_budget_yen", 0, 20000, int),
        "spice_tolerance": _num(form, "spice_tolerance", 0, 5, int),
    }
    sex = form.get("sex")
    if sex not in ("male", "female"):
        raise ValueError("pick male or female (used for the calorie formula)")
    v["sex"] = sex
    v["job"] = form.get("job") if form.get("job") in JOB_LEVELS else "desk"
    v["training_intensity"] = form.get("training_intensity") if form.get("training_intensity") in TRAINING_LEVELS else "moderate"
    v["diet"] = form.get("diet") if form.get("diet") in DIETS else "any"
    v["avoid"] = ",".join(k for k in AVOID_OPTIONS if form.get(f"avoid_{k}"))
    v["allergies"] = (form.get("allergies") or "").strip()[:200]
    v["dislikes"] = (form.get("dislikes") or "").strip()[:200]
    v["flavor_likes"] = ",".join(f for f in FLAVORS if form.get(f"flavor_{f}"))
    v["cuisines_liked"] = ",".join(c for c in CUISINES if form.get(f"cuisine_{c}"))
    v["setup_done"] = 1

    work_days = {d for d in range(7) if form.get(f"work_{d}")}
    gym_days = {d for d in range(7) if form.get(f"gym_{d}")}
    start, end = form.get("work_start") or "09:00", form.get("work_end") or "18:00"
    commute = int(_num(form, "commute_min", 0, 240))
    weekday_effort = form.get("weekday_effort") if form.get("weekday_effort") in dict(EFFORTS) else "low"
    weekend_effort = form.get("weekend_effort") if form.get("weekend_effort") in dict(EFFORTS) else "full"
    schedule = []
    for d in range(7):
        works = d in work_days
        schedule.append({
            "weekday": d, "work_start": start if works else None, "work_end": end if works else None,
            "commute_min": commute if works else 0, "gym": 1 if d in gym_days else 0,
            "effort": weekday_effort if works else weekend_effort,
        })
    return v, schedule


@bp.route("/", methods=["GET", "POST"])
def start():
    s = store.settings()
    if request.method == "POST":
        try:
            values, schedule = parse(request.form)
        except ValueError as e:
            flash(str(e).capitalize() + ".", "error")
            return redirect(url_for("setup.start"))
        db = get_db()
        cols = ", ".join(f"{k} = ?" for k in values)
        db.execute(f"UPDATE settings SET {cols} WHERE id = 1", tuple(values.values()))
        for day in schedule:
            db.execute("UPDATE schedule_days SET work_start = ?, work_end = ?, commute_min = ?, gym = ?, effort = ?"
                       " WHERE weekday = ?", (day["work_start"], day["work_end"], day["commute_min"], day["gym"],
                                              day["effort"], day["weekday"]))
        db.commit()
        first, _ = plans.current_week()
        plans.generate_week(first)
        flash("All set. Here's your week. Tap a meal to see it, swap anything you don't fancy.", "ok")
        return redirect(url_for("plan.week"))

    from ..db import query
    sched = [dict(r) for r in query("SELECT * FROM schedule_days ORDER BY weekday")]
    work = next((d for d in sched if d["work_start"]), None)
    return render_template(
        "setup.html", s=s, jobs=JOB_LEVELS, intensities=TRAINING_LEVELS, diets=DIETS, avoid=AVOID_OPTIONS,
        flavors=FLAVORS, cuisines=CUISINES, paces=PACES, efforts=EFFORTS, weekdays=WEEKDAYS, sched=sched,
        work=work, avoid_on=store.split_list(s.get("avoid")), flavor_on=store.split_list(s["flavor_likes"]),
        cuisine_on=store.split_list(s["cuisines_liked"]),
    )
