import re

from .. import food_rules
from ..staples import BASICS, STAPLES, load as load_staples
from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import plans, store
from ..db import get_db
from ..diet import AVOID_OPTIONS, DIETS
from ..equipment import APPLIANCES
from ..pricing import COUNTRIES, areas, options_json, shops
from ..nutrition import JOB_LEVELS, TRAINING_LEVELS, WALKING_LEVELS
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


def prep_from_form(form):
    """Meal prep days (weekday numbers) and what they cover, from the shared picker."""
    return {"prep_weekdays": ",".join(str(d) for d in range(7) if form.get(f"prep_{d}")),
            "prep_covers": "lunch_dinner" if form.get("prep_covers") == "lunch_dinner" else "lunch"}


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
    v["walking"] = form.get("walking") if form.get("walking") in WALKING_LEVELS else "little"
    v["diet"] = form.get("diet") if form.get("diet") in DIETS else "any"
    v["avoid"] = ",".join(k for k in AVOID_OPTIONS if form.get(f"avoid_{k}"))
    v["allergies"] = (form.get("allergies") or "").strip()[:200]
    v["dislikes"] = (form.get("dislikes") or "").strip()[:200]
    v["flavor_likes"] = ",".join(f for f in FLAVORS if form.get(f"flavor_{f}"))
    v["cuisines_liked"] = ",".join(c for c in CUISINES if form.get(f"cuisine_{c}"))
    v["setup_done"] = 1
    v["schedule_mode"] = "flexible" if form.get("schedule_mode") == "flexible" else "fixed"
    v["prep_days"] = int(_num(form, "prep_days", 0, 4)) if form.get("prep_days") else 2
    v.update(prep_from_form(form))
    v["appliances"] = ",".join(k for k in APPLIANCES if form.get(f"app_{k}"))
    rules = food_rules.from_form(form)
    v["food_rules"] = food_rules.dump(rules)
    from ..staples import from_form as staples_from_form
    v["staples"] = staples_from_form(form)
    if "airfryer" in rules.values() and "air_fryer" not in v["appliances"].split(","):
        v["appliances"] = ",".join(filter(None, [v["appliances"], "air_fryer"]))
    v["about_me"] = (form.get("about_me") or "").strip()[:1000]
    v["country"] = form.get("country") if form.get("country") in COUNTRIES else "JP"
    v["area"] = form.get("area") if form.get("area") in areas(v["country"]) else "city"
    v["shop"] = form.get("shop") if form.get("shop") in shops(v["country"]) else "supermarket"

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
            password, again = request.form.get("password", ""), request.form.get("again", "")
            if password and (len(password) < 6 or password != again):
                raise ValueError("passwords need 6+ characters and must match")
        except ValueError as e:
            flash(str(e).capitalize() + ".", "error")
            return redirect(url_for("setup.start"))
        from .. import profiles
        from .auth import mark_unlocked, set_password
        if (request.form.get("profile_name") or "").strip():
            profiles.rename(profiles.current_id(), request.form["profile_name"])
        if password:
            set_password(password)
            mark_unlocked()
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
    return render_wizard(s, sched)


def render_wizard(s, sched):
    work = next((d for d in sched if d["work_start"]), None)
    return render_template(
        "setup.html", s=s, jobs=JOB_LEVELS, intensities=TRAINING_LEVELS, walking=WALKING_LEVELS, diets=DIETS, avoid=AVOID_OPTIONS,
        appliances=APPLIANCES, app_on=store.split_list(s.get("appliances")),
        countries=COUNTRIES, areas=areas(s.get("country") or "JP"), shops=shops(s.get("country") or "JP"),
        country_options=options_json(),
        food_names=[f["name"] for f in store.foods()],
        flavors=FLAVORS, cuisines=CUISINES, paces=PACES, efforts=EFFORTS, weekdays=WEEKDAYS, sched=sched,
        work=work, avoid_on=store.split_list(s.get("avoid")), flavor_on=store.split_list(s["flavor_likes"]),
        cuisine_on=store.split_list(s["cuisines_liked"]),
        rules=food_rules.load(s), rule_groups=food_rules.GROUPS, rule_options=food_rules.RULES,
        diet_now=s.get("diet") or "any",
        staples=STAPLES, basics=BASICS, staple_prefs=load_staples(s),
    )


def describe_prompt(text):
    return f"""Someone described themselves for a meal-planning app. Pull out ONLY what they actually said.
Leave out any key they didn't mention. Reply with ONE JSON object and nothing else.

Their words:
\"\"\"
{text[:1500]}
\"\"\"

Keys you may use (exact values where listed):
age (number), sex ("male"/"female"), height_cm, weight_kg, goal_weight_kg,
pace ("gentle"/"steady"/"fast"), job ({"/".join(JOB_LEVELS)}), training_days (0-7),
training_intensity ({"/".join(TRAINING_LEVELS)}), schedule_mode ("fixed" or "flexible" if hours change),
work_days (list of 0-6, Monday=0), work_start ("HH:MM"), work_end ("HH:MM"), commute_min,
gym_days (list of 0-6), prep_days (0-4, big cooking sessions a week),
diet ({"/".join(DIETS)}), avoid (list from {", ".join(AVOID_OPTIONS)}),
allergies (text), dislikes (text), spice_tolerance (0-5),
flavors (list from {", ".join(FLAVORS)}), cuisines (list from {", ".join(CUISINES)}),
appliances (list from {", ".join(APPLIANCES)}), weekly_budget_yen, eat_out_slots
"""


def _clamp(value, lo, hi, cast=float):
    try:
        return max(lo, min(hi, cast(float(value))))
    except (TypeError, ValueError):
        return None


def apply_description(data, s, sched):
    """Merge a model's reading of the description into the wizard's values. Every value is checked."""
    s = dict(s)
    sched = [dict(d) for d in sched]
    if not isinstance(data, dict):
        return s, sched
    for key, lo, hi, cast in (("age", 16, 100, int), ("height_cm", 120, 230, float), ("weight_kg", 35, 300, float),
                              ("goal_weight_kg", 35, 300, float), ("training_days", 0, 7, int),
                              ("spice_tolerance", 0, 5, int), ("weekly_budget_yen", 0, 200000, int),
                              ("eat_out_slots", 0, 14, int), ("prep_days", 0, 4, int)):
        if key in data and _clamp(data[key], lo, hi, cast) is not None:
            s[key] = _clamp(data[key], lo, hi, cast)
    choices = {"sex": ("male", "female"), "job": JOB_LEVELS, "training_intensity": TRAINING_LEVELS,
               "diet": DIETS, "schedule_mode": ("fixed", "flexible")}
    for key, allowed in choices.items():
        if data.get(key) in allowed:
            s[key] = data[key]
    pace = {"gentle": 0.25, "steady": 0.5, "fast": 0.75}.get(data.get("pace"))
    if pace:
        s["pace_kg_week"] = pace
    for key, field, allowed in (("avoid", "avoid", AVOID_OPTIONS), ("flavors", "flavor_likes", FLAVORS),
                                ("cuisines", "cuisines_liked", CUISINES), ("appliances", "appliances", APPLIANCES)):
        if isinstance(data.get(key), list):
            s[field] = ",".join(x for x in allowed if x in data[key])
    for key in ("allergies", "dislikes"):
        if isinstance(data.get(key), str):
            s[key] = data[key][:200]

    def days(key):
        return {int(x) for x in data.get(key, []) if str(x).isdigit() and 0 <= int(x) <= 6}             if isinstance(data.get(key), list) else None
    work, gym = days("work_days"), days("gym_days")
    hhmm = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    start = data.get("work_start") if hhmm.match(str(data.get("work_start", ""))) else None
    end = data.get("work_end") if hhmm.match(str(data.get("work_end", ""))) else None
    for d in sched:
        if work is not None:
            d["work_start"] = (start or d["work_start"] or "09:00") if d["weekday"] in work else None
            d["work_end"] = (end or d["work_end"] or "18:00") if d["weekday"] in work else None
        if gym is not None:
            d["gym"] = 1 if d["weekday"] in gym else 0
        if "commute_min" in data and d["work_start"] and _clamp(data["commute_min"], 0, 240, int) is not None:
            d["commute_min"] = _clamp(data["commute_min"], 0, 240, int)
    return s, sched


@bp.route("/describe", methods=["POST"])
def describe():
    from .. import llm
    from ..db import query
    text = (request.form.get("about_me") or "").strip()
    s = store.settings()
    s["about_me"] = text[:1000]
    sched = [dict(r) for r in query("SELECT * FROM schedule_days ORDER BY weekday")]
    p = llm.provider()
    if not text:
        flash("Write a few lines about yourself first.", "error")
    elif p is None:
        flash("No model is set up, so fill the steps in by hand.", "error")
    else:
        try:
            s, sched = apply_description(llm.extract_json(p.complete(describe_prompt(text))), s, sched)
            flash("Filled in from your description. Check each step, nothing is saved yet.", "ok")
        except llm.LLMError as e:
            flash(f"Couldn't read that: {e}. Fill the steps in by hand.", "error")
    return render_wizard(s, sched)
