import json
from datetime import date, datetime

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from .. import planner, plans, store, today, tracking
from ..db import execute, get_db, query, reset_all

bp = Blueprint("track", __name__)


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
        from .. import units
        try:
            kg = round(units.body_in(float(request.form.get("kg", ""))), 1)
            if not 35 <= kg <= 300:
                raise ValueError
        except ValueError:
            flash(f"Enter your weight in {units.body_unit()}, like {units.body(84.6)}.", "error")
            return redirect(url_for("track.progress"))
        execute("INSERT INTO weight_log (date, kg) VALUES (?, ?) ON CONFLICT(date) DO UPDATE SET kg = excluded.kg",
                (today().isoformat(), kg))
        # targets follow the latest weigh-in
        execute("UPDATE settings SET weight_kg = ? WHERE id = 1", (kg,))
        flash(f"Logged {units.body(kg)} {units.body_unit()}. Targets updated.", "ok")
        return redirect(url_for("track.progress"))

    from .. import progress as prog
    from datetime import timedelta
    entries = weights()
    shown = tracking.recent(entries, today(), 90)
    raw, trend, lo, hi = tracking.chart_points(shown)
    s = store.settings()
    targets = store.targets(s)
    water_target = tracking.water_target_ml(s["weight_kg"])
    span = 30 if request.args.get("span") == "30" else 7
    days = prog.daily(today() - timedelta(days=span - 1), today(), s, targets, water_target)
    first_weight = entries[0][1] if entries else None
    latest = entries[-1][1] if entries else s["weight_kg"]
    return render_template("progress.html", entries=list(reversed(shown[-10:])), raw=raw, trend=trend, lo=lo, hi=hi,
                           change=tracking.weekly_change(entries), goal=s["goal_weight_kg"], latest=latest,
                           lost=round(first_weight - latest, 1) if first_weight else None,
                           water_target=water_target, days=days, span=span, sum=prog.summary(days),
                           targets=targets, budget_week=s["weekly_budget_yen"],
                           streaks={"protein": prog.streak(days, "protein_hit"), "water": prog.streak(days, "water_hit"),
                                    "tracked": prog.streak(days, "tracked")})


@bp.route("/cook-now")
def cook_now():
    sim = planner.PantrySim(plans.pantry_lots())
    options = tracking.makeable_now(store.recipes(), sim, today())
    return render_template("cook_now.html", options=options)


@bp.route("/backup")
def backup():
    from .. import datafile
    body = json.dumps(datafile.dump(get_db()), ensure_ascii=False, indent=1)
    return Response(body, mimetype="application/json", headers={
        "Content-Disposition": f"attachment; filename=zettai-backup-{today().isoformat()}.json"})


@bp.route("/restore", methods=["POST"])
def restore():
    from .. import datafile
    upload = request.files.get("file")
    try:
        data = json.loads(upload.read().decode("utf-8")) if upload else None
    except (ValueError, UnicodeDecodeError):
        flash("That file isn't valid JSON. Nothing was changed.", "error")
        return redirect(url_for("settings.edit") + "#reset")
    try:
        datafile.load(get_db(), data)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("settings.edit") + "#reset")
    flash("Backup restored.", "ok")
    return redirect(url_for("main.home"))


@bp.route("/reset", methods=["POST"])
def reset():
    if (request.form.get("confirm") or "").strip().upper() != "RESET":
        flash("Type RESET to confirm. Nothing was deleted.", "error")
        return redirect(url_for("settings.edit"))
    reset_all(get_db(), keep_key=bool(request.form.get("keep_key")))
    flash("Everything was reset. Let's set you up again.", "ok")
    return redirect(url_for("setup.start"))
