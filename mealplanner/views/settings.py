from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import store
from ..db import execute
from ..diet import AVOID_OPTIONS, DIETS
from ..pricing import COUNTRIES, areas, options_json, shops
from ..nutrition import (JOB_LEVELS, MAX_DEFICIT, MAX_PACE_KG_WEEK, TRAINING_LEVELS, activity_multiplier, cm_to_in, in_to_cm,
                         kg_to_lb, lb_to_kg)

bp = Blueprint("settings", __name__, url_prefix="/settings")

# field -> (min, max)
NUMBER_RANGES = {
    "height_cm": (120, 230),
    "weight_kg": (35, 300),
    "goal_weight_kg": (35, 300),
    "age": (16, 100),
    "pace_kg_week": (0, 2),
    "weekly_budget_yen": (0, 200000),
    "eat_out_slots": (0, 14),
    "eat_out_budget_yen": (0, 20000),
    "eat_out_kcal": (0, 2500),
    "snack_kcal": (0, 800),
    "spice_tolerance": (0, 5),
}
INT_FIELDS = {"age", "weekly_budget_yen", "eat_out_slots", "eat_out_budget_yen",
              "eat_out_kcal", "snack_kcal", "spice_tolerance"}
TEXT_FIELDS = ["allergies", "dislikes", "flavor_likes", "cuisines_liked", "cuisines_tired"]
THEMES = {"shokken": "Shokken"}
MODES = {"dark": "Dark", "light": "Light", "system": "Follow phone"}
LOOK_FIELDS = {"theme", "mode", "units", "gemini_key"}


def parse_form(form):
    """Return (values, errors). Body measurements come back in metric."""
    values, errors = {}, []
    units = form.get("units", "metric")
    values["units"] = units if units in ("metric", "imperial") else "metric"

    for field, (lo, hi) in NUMBER_RANGES.items():
        raw = form.get(field, "").strip()
        if raw == "":
            if field == "age":
                values[field] = None
                continue
            errors.append(f"{field.replace('_', ' ')} is required")
            continue
        try:
            num = float(raw)
        except ValueError:
            errors.append(f"{field.replace('_', ' ')} must be a number")
            continue
        if values["units"] == "imperial":
            if field == "height_cm":
                num = in_to_cm(num)
            elif field in ("weight_kg", "goal_weight_kg", "pace_kg_week"):
                num = lb_to_kg(num)
        if not lo <= num <= hi:
            errors.append(f"{field.replace('_', ' ')} must be between {lo} and {hi}")
            continue
        values[field] = int(round(num)) if field in INT_FIELDS else round(num, 2)

    sex = form.get("sex") or None
    values["sex"] = sex if sex in ("male", "female") else None
    job = form.get("job", "desk")
    values["job"] = job if job in JOB_LEVELS else "desk"
    intensity = form.get("training_intensity", "moderate")
    values["training_intensity"] = intensity if intensity in TRAINING_LEVELS else "moderate"
    try:
        values["training_days"] = max(0, min(7, int(form.get("training_days", 3))))
    except ValueError:
        errors.append("training days must be a number")
    d = form.get("diet", "any")
    values["diet"] = d if d in DIETS else "any"
    values["avoid"] = ",".join(k for k in AVOID_OPTIONS if form.get(f"avoid_{k}"))
    for field in TEXT_FIELDS:
        values[field] = form.get(field, "").strip()
    values["goal_mode"] = "deficit" if form.get("goal_mode") == "deficit" else "pace"
    for key, lo, hi, cast in (("deficit_kcal", 0, 1000, int), ("protein_per_kg", 1.2, 2.6, float), ("fat_share", 0.2, 0.4, float)):
        raw = form.get(key)
        if raw not in (None, ""):
            try:
                values[key] = max(lo, min(hi, cast(float(raw))))
            except ValueError:
                errors.append(f"{key.replace('_', ' ')} must be a number")
    values["country"] = form.get("country") if form.get("country") in COUNTRIES else "JP"
    values["area"] = form.get("area") if form.get("area") in areas(values["country"]) else "city"
    values["shop"] = form.get("shop") if form.get("shop") in shops(values["country"]) else "supermarket"
    key = (form.get("gemini_key") or "").strip()
    if key == "-":
        values["gemini_key"] = ""          # "-" clears the saved key
    elif key:
        values["gemini_key"] = key[:200]   # blank keeps the saved key
    theme, mode = form.get("theme"), form.get("mode")
    values["theme"] = "shokken"
    values["mode"] = mode if mode in MODES else "dark"
    from .setup import prep_from_form
    values.update(prep_from_form(form))
    return values, errors


def display_values(s):
    """Settings converted for the form in the chosen unit system."""
    shown = dict(s)
    if s["units"] == "imperial":
        shown["height_cm"] = round(cm_to_in(s["height_cm"]), 1)
        shown["weight_kg"] = round(kg_to_lb(s["weight_kg"]), 1)
        shown["goal_weight_kg"] = round(kg_to_lb(s["goal_weight_kg"]), 1)
        shown["pace_kg_week"] = round(kg_to_lb(s["pace_kg_week"]), 2)
    return shown


def on_settings_changed():
    """Changing any setting re-plans the rest of the current week."""
    from ..plans import replan_if_planned
    if replan_if_planned():
        flash("This week's plan was updated to match.", "ok")


@bp.route("/", methods=["GET", "POST"])
def edit():
    if request.method == "POST":
        values, errors = parse_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            before = store.settings()
            cols = ", ".join(f"{k} = ?" for k in values)
            execute(f"UPDATE settings SET {cols} WHERE id = 1", list(values.values()))
            if values.get("goal_mode") == "deficit" and values.get("deficit_kcal", 0) > MAX_DEFICIT:
                flash(f"A deficit over {MAX_DEFICIT} kcal is capped for safety.", "warn")
            if values["pace_kg_week"] > MAX_PACE_KG_WEEK:
                flash(f"Pace is capped at {MAX_PACE_KG_WEEK} kg/week for safety.", "warn")
            if any(before[k] != v for k, v in values.items() if k not in LOOK_FIELDS):
                on_settings_changed()
            flash("Settings saved.", "ok")
            return redirect(url_for("settings.edit"))

    s = store.settings()
    return render_template(
        "settings.html",
        s=display_values(s),
        targets=store.targets(s),
        jobs=JOB_LEVELS,
        intensities=TRAINING_LEVELS,
        diets=DIETS,
        avoid_options=AVOID_OPTIONS,
        avoid_on=store.split_list(s.get("avoid")),
        multiplier=activity_multiplier(s["job"], s["training_days"], s["training_intensity"]),
        themes=THEMES,
        modes=MODES,
        countries=COUNTRIES,
        areas=areas(s.get("country") or "JP"),
        shops=shops(s.get("country") or "JP"),
        country_options=options_json(),
        max_deficit=MAX_DEFICIT,
        lock_on=bool(s.get("password_hash")),
        food_names=[f["name"] for f in store.foods()],
        has_key=bool(s.get("gemini_key")),
        max_pace=MAX_PACE_KG_WEEK,
    )


@bp.route("/mode", methods=["POST"])
def mode():
    """The moon/sun button in the header: remember dark or light."""
    value = request.form.get("mode")
    if value not in MODES:
        return {"error": "unknown mode"}, 400
    execute("UPDATE settings SET mode = ? WHERE id = 1", (value,))
    return {"mode": value}
