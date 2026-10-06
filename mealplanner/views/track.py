import json
from datetime import date, datetime

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from .. import planner, plans, store, today, tracking
from ..db import execute, get_db, query, reset_all

bp = Blueprint("track", __name__)

# tables included in a backup; the AI key is left out on purpose
BACKUP_SKIP_COLUMNS = {"settings": {"gemini_key"}}


def water_today():
    row = query("SELECT ml FROM water_log WHERE date = ?", (today().isoformat(),), one=True)
    return row["ml"] if row else 0


def weights():
    return [(date.fromisoformat(r["date"]), r["kg"]) for r in query("SELECT * FROM weight_log ORDER BY date")]


@bp.route("/water", methods=["POST"])
def water():
    step = tracking.GLASS_ML if request.form.get("change") != "minus" else -tracking.GLASS_ML
    ml = max(0, water_today() + step)
    execute("INSERT INTO water_log (date, ml) VALUES (?, ?) ON CONFLICT(date) DO UPDATE SET ml = excluded.ml",
            (today().isoformat(), ml))
    return redirect(request.referrer or url_for("main.home"))


@bp.route("/progress", methods=["GET", "POST"])
def progress():
    if request.method == "POST":
        try:
            kg = round(float(request.form.get("kg", "")), 1)
            if not 35 <= kg <= 300:
                raise ValueError
        except ValueError:
            flash("Enter your weight in kg, like 84.6.", "error")
            return redirect(url_for("track.progress"))
        execute("INSERT INTO weight_log (date, kg) VALUES (?, ?) ON CONFLICT(date) DO UPDATE SET kg = excluded.kg",
                (today().isoformat(), kg))
        # targets follow the latest weigh-in
        execute("UPDATE settings SET weight_kg = ? WHERE id = 1", (kg,))
        flash(f"Logged {kg} kg. Targets updated.", "ok")
        return redirect(url_for("track.progress"))

    entries = weights()
    shown = tracking.recent(entries, today(), 90)
    raw, trend, lo, hi = tracking.chart_points(shown)
    s = store.settings()
    water_week = {r["date"]: r["ml"] for r in query("SELECT * FROM water_log")}
    week = [(d, water_week.get(d.isoformat(), 0)) for d in tracking.week_dates(today())]
    return render_template("progress.html", entries=list(reversed(shown[-10:])), raw=raw, trend=trend, lo=lo, hi=hi,
                           change=tracking.weekly_change(entries), goal=s["goal_weight_kg"],
                           latest=entries[-1][1] if entries else s["weight_kg"],
                           water_week=week, water_target=tracking.water_target_ml(s["weight_kg"]))


@bp.route("/cook-now")
def cook_now():
    sim = planner.PantrySim(plans.pantry_lots())
    options = tracking.makeable_now(store.recipes(), sim, today())
    return render_template("cook_now.html", options=options)


@bp.route("/backup")
def backup():
    data = {"exported": datetime.now().isoformat(timespec="seconds"), "tables": {}}
    for row in query("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
        name = row["name"]
        skip = BACKUP_SKIP_COLUMNS.get(name, set())
        data["tables"][name] = [{k: v for k, v in dict(r).items() if k not in skip}
                                for r in query(f"SELECT * FROM {name}")]
    body = json.dumps(data, ensure_ascii=False, indent=1)
    return Response(body, mimetype="application/json", headers={
        "Content-Disposition": f"attachment; filename=meal-planner-backup-{today().isoformat()}.json"})


@bp.route("/reset", methods=["POST"])
def reset():
    if (request.form.get("confirm") or "").strip().upper() != "RESET":
        flash("Type RESET to confirm. Nothing was deleted.", "error")
        return redirect(url_for("settings.edit"))
    reset_all(get_db(), keep_key=bool(request.form.get("keep_key")))
    flash("Everything was reset. Let's set you up again.", "ok")
    return redirect(url_for("setup.start"))
