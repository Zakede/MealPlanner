from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import store
from ..db import execute
from ..nutrition import ACTIVITY_LEVELS, MAX_PACE_KG_WEEK, cm_to_in, in_to_cm, kg_to_lb, lb_to_kg

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
    "spice_tolerance": (1, 5),
}
INT_FIELDS = {"age", "weekly_budget_yen", "eat_out_slots", "eat_out_budget_yen",
              "eat_out_kcal", "snack_kcal", "spice_tolerance"}
TEXT_FIELDS = ["allergies", "dislikes", "flavor_likes", "cuisines_liked", "cuisines_tired"]
THEMES = {"apothecary": "Apothecary", "wakatake": "Wakatake + Momo"}
MODES = {"dark": "Dark", "light": "Light", "system": "Follow phone"}
LOOK_FIELDS = {"theme", "mode", "units"}


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
    activity = form.get("activity", "light")
    values["activity"] = activity if activity in ACTIVITY_LEVELS else "light"
    for field in TEXT_FIELDS:
        values[field] = form.get(field, "").strip()
    theme, mode = form.get("theme"), form.get("mode")
    values["theme"] = theme if theme in THEMES else "apothecary"
    values["mode"] = mode if mode in MODES else "dark"
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
        activity_levels=ACTIVITY_LEVELS,
        themes=THEMES,
        modes=MODES,
        max_pace=MAX_PACE_KG_WEEK,
    )
