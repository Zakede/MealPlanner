import re

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import store
from ..db import get_db, query
from ..schedule import WEEKDAYS, slot_limits
from . import settings as settings_view

bp = Blueprint("schedule", __name__, url_prefix="/schedule")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
EFFORTS = [("none", "None (no cooking)"), ("low", "Low (15 min max)"), ("full", "Full (batch cooking ok)")]


def _time(values, key, label, required=True):
    value = (values.get(key) or "").strip()
    if not value:
        if required:
            raise ValueError(f"{label}: {key.replace('_', ' ')} is required")
        return None
    if not TIME.match(value):
        raise ValueError(f"{label}: {key.replace('_', ' ')} must look like 07:30")
    return value


def parse_day(form, wd):
    prefix = f"d{wd}_"
    values = {k[len(prefix):]: v for k, v in form.items() if k.startswith(prefix)}
    label = WEEKDAYS[wd]
    work_start = _time(values, "work_start", label, False)
    work_end = _time(values, "work_end", label, False)
    if bool(work_start) != bool(work_end):
        raise ValueError(f"{label}: set both work start and end, or neither")
    try:
        commute = int(values.get("commute_min") or 0)
    except ValueError:
        raise ValueError(f"{label}: commute must be in minutes")
    effort = values.get("effort", "low")
    return {
        "wake": _time(values, "wake", label),
        "work_start": work_start,
        "work_end": work_end,
        "commute_min": max(0, min(commute, 240)),
        "gym": 1 if values.get("gym") else 0,
        "breakfast_time": _time(values, "breakfast_time", label),
        "lunch_time": _time(values, "lunch_time", label),
        "dinner_time": _time(values, "dinner_time", label),
        "effort": effort if effort in ("none", "low", "full") else "low",
        "away": 1 if values.get("away") else 0,
    }


def parse_mode(form):
    """Regular hours or "it changes" (shifts, random days), and how many big cooks a week in that mode."""
    s = store.settings()
    mode = "flexible" if form.get("schedule_mode") == "flexible" else "fixed"
    try:
        prep = int(form.get("prep_days") or s.get("prep_days") or 0)
    except ValueError:
        raise ValueError("Big cook sessions must be a number")
    return {"schedule_mode": mode, "prep_days": max(0, min(prep, 4))}


@bp.route("/", methods=["GET", "POST"])
def edit():
    if request.method == "POST":
        try:
            days = [parse_day(request.form, wd) for wd in range(7)]
            mode = parse_mode(request.form)
        except ValueError as e:
            flash(str(e), "error")
        else:
            db = get_db()
            db.execute("UPDATE settings SET schedule_mode = ?, prep_days = ? WHERE id = 1",
                       (mode["schedule_mode"], mode["prep_days"]))
            for wd, d in enumerate(days):
                cols = ", ".join(f"{k} = ?" for k in d)
                db.execute(f"UPDATE schedule_days SET {cols} WHERE weekday = ?", (*d.values(), wd))
            db.commit()
            settings_view.on_settings_changed()
            flash("Schedule saved.", "ok")
            return redirect(url_for("schedule.edit"))
    days = [dict(r) for r in query("SELECT * FROM schedule_days ORDER BY weekday")]
    for d in days:
        d["limits"] = slot_limits(d)
    return render_template("schedule.html", days=days, names=WEEKDAYS, efforts=EFFORTS, s=store.settings())
