from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import budget, logbook, plans, store, today
from ..db import execute, query
from ..extras import WORKOUT_METS, best_picks, combo_for, workout_kcal

bp = Blueprint("extras", __name__)
SLOTS = ("breakfast", "lunch", "dinner", "snack")


def _int(form, key, lo, hi, default=None):
    raw = (form.get(key) or "").strip()
    if raw == "":
        if default is None:
            raise ValueError(f"{key} is required")
        return default
    try:
        value = int(float(raw))
    except ValueError:
        raise ValueError(f"{key} must be a number")
    if not lo <= value <= hi:
        raise ValueError(f"{key} must be between {lo} and {hi}")
    return value


def _date(form):
    try:
        return date.fromisoformat(form.get("date") or today().isoformat())
    except ValueError:
        raise ValueError("date looks wrong")


@bp.route("/snacks", methods=["GET", "POST"])
def snacks():
    if request.method == "POST":
        craving, swap = (request.form.get("craving") or "").strip(), (request.form.get("swap") or "").strip()
        if not craving or not swap:
            flash("Fill in both the craving and the swap.", "error")
        else:
            try:
                kcal_from = _int(request.form, "kcal_from", 0, 3000, 0) or None
                kcal_to = _int(request.form, "kcal_to", 0, 3000, 0) or None
            except ValueError as e:
                flash(str(e), "error")
            else:
                execute("INSERT INTO craving_swaps (craving, swap, kcal_from, kcal_to, note) VALUES (?, ?, ?, ?, ?)",
                        (craving[:60], swap[:80], kcal_from, kcal_to, (request.form.get("note") or "")[:120]))
                flash("Swap added.", "ok")
        return redirect(url_for("extras.snacks"))
    swaps = query("SELECT * FROM craving_swaps ORDER BY craving")
    snack_recipes = [r for r in store.recipes() if "snack" in r["type_list"]]
    snack_recipes.sort(key=lambda r: -r["per_serving"]["protein"] / max(1, r["per_serving"]["kcal"]))
    return render_template("snacks.html", swaps=swaps, snacks=snack_recipes, allowance=store.settings()["snack_kcal"])


@bp.route("/snacks/<int:swap_id>/delete", methods=["POST"])
def delete_swap(swap_id):
    execute("DELETE FROM craving_swaps WHERE id = ?", (swap_id,))
    return redirect(url_for("extras.snacks"))


def kcal_left_today():
    on = today()
    row = query("SELECT kcal_target FROM plan_days WHERE date = ?", (on.isoformat(),), one=True)
    targets = store.targets()
    target = row["kcal_target"] if row else (targets.kcal if targets else 2000)
    eaten = sum(m["kcal"] for m in plans.meals_between(on, on) if m["status"] in ("cooked", "eaten", "eaten_out"))
    out = query("SELECT COALESCE(SUM(kcal), 0) k FROM eating_out_log WHERE date = ?", (on.isoformat(),), one=True)["k"]
    return max(0, round(target - eaten - out))


@bp.route("/eat-out", methods=["GET", "POST"])
def eat_out():
    if request.method == "POST":
        try:
            on = _date(request.form)
            slot = request.form.get("slot")
            if slot not in SLOTS:
                raise ValueError("pick a meal")
            kcal = _int(request.form, "kcal", 0, 4000)
            protein = _int(request.form, "protein", 0, 300, 0)
            yen = _int(request.form, "yen", 0, 50000, 0)
        except ValueError as e:
            flash(str(e).capitalize() + ".", "error")
            return redirect(url_for("extras.eat_out"))
        notes = logbook.log_eat_out(on, slot, (request.form.get("place") or "")[:60],
                                    (request.form.get("item") or "")[:80], kcal, protein, yen)
        flash("Logged. " + " ".join(notes), "ok")
        return redirect(url_for("extras.eat_out"))

    s = store.settings()
    room = request.args.get("kcal", type=int) or min(kcal_left_today() or s["eat_out_kcal"], s["eat_out_kcal"] + 200)
    picks = [dict(r) for r in query("SELECT * FROM quick_picks")]
    chains = sorted({p["chain"] for p in picks})
    first, last = budget.week_bounds(today())
    log = query("SELECT * FROM eating_out_log WHERE date BETWEEN ? AND ? ORDER BY date DESC, id DESC",
                (first.isoformat(), last.isoformat()))
    return render_template("eat_out.html", room=room, today=today(), slots=SLOTS, log=log,
                           combos={c: combo_for([p for p in picks if p["chain"] == c], room) for c in chains},
                           best=best_picks(picks, room), budget=plans.week_budget(first),
                           slots_left=max(0, s["eat_out_slots"] - plans.eat_out_used(first, last)))


@bp.route("/spending")
def spending():
    first, _ = budget.week_bounds(today())
    return render_template("spending.html", sp=logbook.spending(first), changes=logbook.price_changes())


@bp.route("/workouts", methods=["GET", "POST"])
def workouts():
    s = store.settings()
    if request.method == "POST":
        try:
            on = _date(request.form)
            kind = request.form.get("kind") if request.form.get("kind") in WORKOUT_METS else "other"
            minutes = _int(request.form, "minutes", 1, 600)
            effort = _int(request.form, "effort", 1, 10, 6)
            known = _int(request.form, "kcal", 0, 5000, 0)
        except ValueError as e:
            flash(str(e).capitalize() + ".", "error")
            return redirect(url_for("extras.workouts"))
        kcal = known or workout_kcal(kind, minutes, effort, s["weight_kg"])
        execute("INSERT INTO workouts (date, kind, minutes, effort, kcal, kcal_estimated, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (on.isoformat(), kind, minutes, effort, kcal, 0 if known else 1, (request.form.get("note") or "")[:120]))
        flash(f"Logged {minutes} min of {kind}, about {kcal} kcal.", "ok")
        return redirect(url_for("extras.workouts"))
    first, last = budget.week_bounds(today())
    week = logbook.workouts_between(first, last)
    return render_template("workouts.html", week=week, kinds=WORKOUT_METS, today=today(),
                           minutes=sum(w["minutes"] for w in week), kcal=sum(w["kcal"] for w in week),
                           earlier=logbook.workouts_between(first - timedelta(days=28), first - timedelta(days=1)))


@bp.route("/workouts/<int:workout_id>/delete", methods=["POST"])
def delete_workout(workout_id):
    execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
    return redirect(url_for("extras.workouts"))
