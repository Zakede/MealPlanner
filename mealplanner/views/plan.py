import re
from datetime import date as date_cls, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .. import plans, store, today

bp = Blueprint("plan", __name__, url_prefix="/plan")


def selected_week():
    first, _ = plans.current_week()
    if request.values.get("week") == "next":
        first += timedelta(days=7)
    return first


def back(first):
    current, _ = plans.current_week()
    return redirect(url_for("plan.week", week="next" if first > current else None))


@bp.route("/")
def week():
    first = selected_week()
    days = plans.day_summaries(first)
    grid_order = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3}
    for d in days:
        d["meals"] = sorted(d["meals"], key=lambda m: (grid_order[m["slot"]], m["id"]))
    meals = [m for d in days for m in d["meals"]]
    infos = plans.build_days([d["date"] for d in days])
    for d in days:
        d["info"] = infos[d["date"]]
    return render_template(
        "plan/week.html",
        first=first,
        is_next=request.args.get("week") == "next",
        days=days,
        today=today(),
        has_plan=bool(meals),
        drafts=sum(1 for m in meals if m["status"] == "draft"),
        flagged=sum(1 for m in meals if m["replace_flag"] and m["status"] in plans.EDITABLE),
        budget=plans.week_budget(first),
        needs_profile=store.targets() is None,
        can_undo=bool(plans.query("SELECT 1 FROM plan_actions WHERE undone = 0 LIMIT 1")),
    )


@bp.route("/generate", methods=["POST"])
def generate():
    first = selected_week()
    try:
        meals = plans.generate_week(first)
    except ValueError as e:
        flash(str(e), "error")
    else:
        flash(f"Drafted {len(meals)} meals. Mark any you want swapped, then approve.", "ok")
    return back(first)


@bp.route("/meal/<int:meal_id>/replace", methods=["POST"])
def toggle_replace(meal_id):
    plans.set_replace(meal_id, request.form.get("flag") == "1")
    return back(selected_week())


@bp.route("/replace", methods=["POST"])
def replace():
    first = selected_week()
    n = plans.replace_flagged(first)
    flash(f"Replaced {n} meal{'s' if n != 1 else ''}." if n else "Nothing was marked to replace.", "ok")
    return back(first)


@bp.route("/approve", methods=["POST"])
def approve():
    first = selected_week()
    plans.approve_week(first)
    flash("Week approved. Shopping list is ready.", "ok")
    return redirect(url_for("plan.shopping", week=request.values.get("week")))


@bp.route("/push-back", methods=["POST"])
def push_back():
    days = 2 if request.form.get("days") == "2" else 1
    if plans.push_back(days):
        flash(f"Tonight and everything after moved {days} day{'s' if days > 1 else ''} later.", "ok")
    else:
        flash("Nothing left to push back.", "warn")
    return redirect(request.referrer or url_for("plan.week"))


@bp.route("/undo", methods=["POST"])
def undo():
    flash("Undone." if plans.undo_last() else "Nothing to undo.", "ok")
    return redirect(request.referrer or url_for("plan.week"))


@bp.route("/add", methods=["GET", "POST"])
def add():
    from .. import diet
    if request.method == "POST":
        try:
            on = date_cls.fromisoformat(request.form.get("date", ""))
            slot = request.form.get("slot")
            if slot not in ("breakfast", "lunch", "dinner", "snack"):
                raise ValueError("pick a meal")
            plans.add_meal(on, slot, int(request.form.get("recipe_id", 0)))
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("plan.add", date=request.form.get("date"), slot=request.form.get("slot")))
        flash("Added.", "ok")
        current, _ = plans.current_week()
        return redirect(url_for("plan.week", week="next" if on >= current + timedelta(days=7) else None))
    on = request.args.get("date") or today().isoformat()
    slot = request.args.get("slot", "dinner")
    s = store.settings()
    prefs = store.recipe_prefs()
    avoid = store.split_list(s.get("avoid"))
    options = [r for r in store.recipes() if slot in r["type_list"] and prefs.get(r["id"]) != "never"
               and diet.allowed(r, s.get("diet") or "any", avoid)]
    options.sort(key=lambda r: (prefs.get(r["id"]) != "favorite", r["name"]))
    return render_template("plan/add.html", on=on, slot=slot, options=options, prefs=prefs)


@bp.route("/day/<day>", methods=["GET", "POST"])
def day(day):
    try:
        on = date_cls.fromisoformat(day)
    except ValueError:
        return redirect(url_for("plan.week"))
    if request.method == "POST":
        f = request.form
        hhmm = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
        mode = f.get("work_mode") if f.get("work_mode") in ("usual", "off", "work") else "usual"
        start, end = f.get("work_start", ""), f.get("work_end", "")
        if mode == "work" and not (hhmm.match(start) and hhmm.match(end)):
            flash("Give work a start and end time, like 09:00 and 18:00.", "error")
            return redirect(url_for("plan.day", day=day))
        try:
            commute = max(0, min(240, int(f.get("commute_min") or 0)))
        except ValueError:
            commute = 0
        effort = f.get("effort") if f.get("effort") in ("none", "low", "full") else None
        plans.set_override(
            on,
            work_mode=None if mode == "usual" else mode,
            work_start=start if mode == "work" else None,
            work_end=end if mode == "work" else None,
            commute_min=commute if mode == "work" else None,
            gym={"yes": 1, "no": 0}.get(f.get("gym")),
            away={"yes": 1, "no": 0}.get(f.get("away")),
            effort=effort,
            note=(f.get("note") or "").strip()[:140] or None,
        )
        if store.targets() is not None:
            plans.replan_rest_of_day(on)
        flash(f"{on.strftime('%A')} updated and re-planned.", "ok")
        current, _ = plans.current_week()
        return redirect(url_for("plan.week", week="next" if on >= current + timedelta(days=7) else None))
    info = plans.build_days([on])[on]
    o = plans.override(on)
    return render_template("plan/day.html", on=on, info=info, o=o)


@bp.route("/shopping")
def shopping():
    first = selected_week()
    items = plans.shopping_list(first)
    last = first + timedelta(days=6)
    drafts = [m for m in plans.meals_between(first, last) if m["status"] == "draft"]
    preview = not items and bool(drafts)
    if preview:
        items = plans.shopping_preview(first)
    return render_template("plan/shopping.html", items=items, first=first, preview=preview,
                           has_plan=bool(plans.meals_between(first, last)),
                           is_next=request.args.get("week") == "next",
                           total=sum(i["est_cost"] for i in items if not i["checked"]),
                           budget=plans.week_budget(first))


@bp.route("/shopping/<int:item_id>/bought", methods=["POST"])
def bought(item_id):
    raw = (request.form.get("price") or "").strip()
    price = int(raw) if raw.isdigit() else None
    plans.add_bought_to_pantry(selected_week(), item_id, price)
    return redirect(url_for("plan.shopping", week=request.values.get("week")))


@bp.route("/api/week")
def api_week():
    first = selected_week()
    days = plans.day_summaries(first)
    for d in days:
        d["date"] = d["date"].isoformat()
        for m in d["meals"]:
            m["date"] = m["date"].isoformat()
            m.pop("recipe", None)
    return jsonify({"week_start": first.isoformat(), "days": days, "budget": plans.week_budget(first)})
