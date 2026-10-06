from datetime import timedelta

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
    meals = [m for d in days for m in d["meals"]]
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


@bp.route("/shopping")
def shopping():
    first = selected_week()
    items = plans.shopping_list(first)
    return render_template("plan/shopping.html", items=items, first=first,
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
