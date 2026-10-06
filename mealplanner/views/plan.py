import re
from datetime import date as date_cls, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .. import plans, store, today
from ..db import execute

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
        job=store.settings().get("job") or "desk",
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
            work_kind=f.get("work_kind") if mode == "work" and f.get("work_kind") in ("desk", "standing", "physical") else None,
        )
        if store.targets() is not None:
            plans.replan_from(on)
            row = plans.query("SELECT kcal_target, protein_target FROM plan_days WHERE date = ?", (on.isoformat(),), one=True)
            target = f" Target {row['kcal_target']} kcal, {row['protein_target']} g protein." if row else ""
            flash(f"{on.strftime('%A')} updated; the rest of the week re-planned around it.{target}", "ok")
        else:
            flash(f"{on.strftime('%A')} saved.", "ok")
        current, _ = plans.current_week()
        return redirect(url_for("plan.week", week="next" if on >= current + timedelta(days=7) else None))
    info = plans.build_days([on])[on]
    o = plans.override(on)
    target = plans.query("SELECT kcal_target, protein_target FROM plan_days WHERE date = ?", (on.isoformat(),), one=True)
    return render_template("plan/day.html", on=on, info=info, o=o, target=target, job=store.settings().get("job"))


@bp.route("/day/<day>/work", methods=["POST"])
def work(day):
    """The 'Got work' tick on the week page: tick it and give the hours, untick for a day off."""
    try:
        on = date_cls.fromisoformat(day)
    except ValueError:
        return redirect(url_for("plan.week"))
    f = request.form
    hhmm = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    if f.get("work"):
        start, end = f.get("work_start", ""), f.get("work_end", "")
        if not (hhmm.match(start) and hhmm.match(end)):
            flash("Give work a start and end time, like 09:00 and 18:00.", "error")
            return redirect(url_for("plan.day", day=day))
        kind = f.get("work_kind") if f.get("work_kind") in ("desk", "standing", "physical") else None
        plans.set_override(on, work_mode="work", work_start=start, work_end=end, work_kind=kind)
        what = f"work {start}–{end}"
    else:
        plans.set_override(on, work_mode="off", work_start=None, work_end=None, commute_min=None, work_kind=None)
        what = "a day off"
    if store.targets() is not None and plans.query("SELECT 1 FROM plan_meals WHERE date >= ? LIMIT 1",
                                                   (on.isoformat(),), one=True):
        plans.replan_from(on)
        flash(f"{on.strftime('%A')} is now {what}; the rest of the week re-planned.", "ok")
    else:
        flash(f"{on.strftime('%A')} is now {what}.", "ok")
    current, _ = plans.current_week()
    return redirect(url_for("plan.week", week="next" if on >= current + timedelta(days=7) else None))


SECTIONS = [
    ("Meat & fish", {"poultry", "meat", "fish", "seafood"}),
    ("Vegetables & fruit", {"veg", "fruit"}),
    ("Dairy & eggs", {"dairy", "egg"}),
    ("Tofu & beans", {"soy", "legume"}),
    ("Rice, bread & noodles", {"grain"}),
    ("Sauces & staples", {"sauce", "fat", "snack", ""}),
]


def buy_amount(item):
    """What to actually pick up: pieces when we know them, else grams rounded up to a pack-ish size."""
    g = item["grams"]
    if item.get("piece_g"):
        pcs = max(1, -(-g // item["piece_g"]))
        return f"{int(pcs)} pc{'s' if pcs > 1 else ''}"
    step = 50 if g <= 300 else 100 if g <= 1000 else 250
    return f"{int(-(-g // step) * step)} g"


@bp.route("/shopping")
def shopping():
    first = selected_week()
    items = plans.shopping_list(first)
    last = first + timedelta(days=6)
    drafts = [m for m in plans.meals_between(first, last) if m["status"] == "draft"]
    preview = not items and bool(drafts)
    if preview:
        items = plans.shopping_preview(first)
    for i in items:
        i["buy"] = buy_amount(i)
    sections = []
    for title, cats in SECTIONS:
        rows = [i for i in items if (i.get("category") or "") in cats]
        if rows:
            sections.append((title, sorted(rows, key=lambda r: (r["checked"], r["name"]))))
    extras = plans.shopping_extras(first)
    skipped_ids = plans.skipped_foods(first)
    skipped = [store.food(fid) for fid in skipped_ids]
    total = sum(i["est_cost"] for i in items if not i["checked"]) + sum(e["est_cost"] for e in extras if not e["checked"])
    return render_template("plan/shopping.html", sections=sections, extras=extras, skipped=[f for f in skipped if f],
                           first=first, preview=preview, has_plan=bool(plans.meals_between(first, last)),
                           is_next=request.args.get("week") == "next", total=total, budget=plans.week_budget(first),
                           count=sum(1 for i in items if not i["checked"]) + sum(1 for e in extras if not e["checked"]))


@bp.route("/shopping/skip/<int:food_id>", methods=["POST"])
def skip(food_id):
    plans.skip_food(selected_week(), food_id, skip=request.form.get("undo") != "1")
    return redirect(url_for("plan.shopping", week=request.values.get("week")))


@bp.route("/shopping/extra", methods=["POST"])
def extra():
    first = selected_week()
    name = (request.form.get("name") or "").strip()[:60]
    if not name:
        flash("Type what you want to buy.", "error")
    else:
        try:
            cost = max(0, int(float(request.form.get("cost") or 0)))
        except ValueError:
            cost = 0
        execute("INSERT INTO shopping_extra (week_start, name, amount, est_cost) VALUES (?, ?, ?, ?)",
                      (first.isoformat(), name, (request.form.get("amount") or "").strip()[:30], cost))
    return redirect(url_for("plan.shopping", week=request.values.get("week")))


@bp.route("/shopping/extra/<int:extra_id>/<action>", methods=["POST"])
def extra_action(extra_id, action):
    if action == "toggle":
        execute("UPDATE shopping_extra SET checked = 1 - checked WHERE id = ?", (extra_id,))
    elif action == "delete":
        execute("DELETE FROM shopping_extra WHERE id = ?", (extra_id,))
    return redirect(url_for("plan.shopping", week=request.values.get("week")))


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
