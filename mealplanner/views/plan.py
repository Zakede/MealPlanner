import re
from datetime import date as date_cls, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from .. import plans, store, today
from ..db import execute
from ..nutrition import activity_burn

bp = Blueprint("plan", __name__, url_prefix="/plan")


def store_cur():
    from ..pricing import currency
    return currency(store.settings())


def selected_week():
    first, _ = plans.current_week()
    if request.values.get("week") == "next":
        first += timedelta(days=7)
    return first


def add_burn(info):
    """Put an 'about N kcal' estimate on each activity of a day."""
    t = store.targets()
    for b in info["blocks"]:
        b["burn"] = activity_burn(t.bmr, b["intensity"], b["hours"], b["kind"]) if t else 0
    return info


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
        d["info"] = add_burn(infos[d["date"]])
    t = store.targets()
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
        kinds=ACTIVITY_KINDS,
        saved=plans.saved_activities(),
        bmr=round(t.bmr) if t else 0,
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
    from .. import llm
    picks = [dict(r) for r in plans.query("SELECT * FROM quick_picks ORDER BY chain, item")]
    snacks = [r for r in options if slot == "snack"] or [r for r in store.recipes() if "snack" in r["type_list"]
                                                          and prefs.get(r["id"]) != "never"]
    return render_template("plan/add.html", on=on, slot=slot, options=options, prefs=prefs, picks=picks,
                           snacks=snacks, tab=request.args.get("tab") or "recipes", ai=llm.provider() is not None)


def _add_target():
    on = date_cls.fromisoformat(request.form.get("date", ""))
    slot = request.form.get("slot")
    return on, slot


def _after_add(on, title):
    flash(f"{title} added.", "ok")
    current, _ = plans.current_week()
    return redirect(url_for("plan.week", week="next" if on >= current + timedelta(days=7) else None))


@bp.route("/add/pick/<int:pick_id>", methods=["POST"])
def add_pick(pick_id):
    """A konbini or chain item into the plan."""
    p = plans.query("SELECT * FROM quick_picks WHERE id = ?", (pick_id,), one=True)
    try:
        on, slot = _add_target()
        if not p:
            raise ValueError("that item is gone")
        plans.add_simple_meal(on, slot, f"{p['item']} ({p['chain']})", p["kcal"], p["protein"], cost=p["yen"])
    except ValueError as e:
        flash(str(e).capitalize() + ".", "error")
        return redirect(url_for("plan.add", date=request.form.get("date"), slot=request.form.get("slot"), tab="picks"))
    return _after_add(on, p["item"])


@bp.route("/add/custom", methods=["POST"])
def add_custom():
    """Anything typed in: a name and its numbers (guessed or yours)."""
    f = request.form
    try:
        on, slot = _add_target()
        name = (f.get("name") or "").strip()
        if not name:
            raise ValueError("give it a name")
        nums = {}
        for key, hi in (("kcal", 3000), ("protein", 200), ("carbs", 400), ("fat", 200), ("cost", 100000)):
            raw = (f.get(key) or "").strip()
            nums[key] = max(0.0, min(hi, float(raw))) if raw else 0.0
        if nums["kcal"] <= 0:
            raise ValueError("add the calories, or tap Guess")
        plans.add_simple_meal(on, slot, name, nums["kcal"], nums["protein"], nums["carbs"], nums["fat"],
                              round(nums["cost"]), kind="eat_out" if f.get("out") else "konbini")
    except ValueError as e:
        flash(str(e).capitalize() + ".", "error")
        return redirect(url_for("plan.add", date=f.get("date"), slot=f.get("slot"), tab="type"))
    return _after_add(on, name)


@bp.route("/add/guess")
def add_guess():
    """Calories for something typed in: a known konbini item first, then the AI helper."""
    from .. import llm
    from ..pricing import currency
    from .foodlog import check_estimate, estimate_prompt
    text = (request.args.get("text") or "").strip()[:200]
    if not text:
        return jsonify({"error": "Type what it is first."}), 400
    low = text.lower()
    for p in plans.query("SELECT * FROM quick_picks"):
        if p["item"].lower() in low or low in p["item"].lower():
            return jsonify({"name": p["item"], "kcal": p["kcal"], "protein": p["protein"], "carbs": 0, "fat": 0,
                            "price": p["yen"], "source": "list"})
    provider = llm.provider()
    if provider is None:
        return jsonify({"error": "Not in the konbini list, and no AI helper is set up (Settings → AI helper)."}), 404
    try:
        est = check_estimate(llm.extract_json(provider.complete(estimate_prompt(text, currency(store.settings())))))
    except llm.LLMError as e:
        return jsonify({"error": f"AI helper: {e}."}), 502
    if not est:
        return jsonify({"error": "That guess didn't add up. Type the numbers yourself."}), 502
    return jsonify(dict(est, source="ai"))


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
    info = add_burn(plans.build_days([on])[on])
    o = plans.override(on)
    target = plans.query("SELECT kcal_target, protein_target FROM plan_days WHERE date = ?", (on.isoformat(),), one=True)
    return render_template("plan/day.html", on=on, info=info, o=o, target=target, job=store.settings().get("job"),
                           parts=plans.target_parts(on))


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
    return after_day_change(on, f"{on.strftime('%A')} is now {what}")


def after_day_change(on, message):
    """Re-plan from a changed day if there's a plan to change, then back to that week."""
    if store.targets() is not None and plans.query("SELECT 1 FROM plan_meals WHERE date >= ? LIMIT 1",
                                                   (on.isoformat(),), one=True):
        plans.replan_from(on)
        flash(f"{message}; the rest of the week re-planned.", "ok")
    else:
        flash(f"{message}.", "ok")
    current, _ = plans.current_week()
    return redirect(url_for("plan.week", week="next" if on >= current + timedelta(days=7) else None))


ACTIVITY_KINDS = {"work": "Work", "school": "School", "parttime": "Part-time", "club": "Club",
                  "gym": "Gym / sport", "other": "Other"}
INTENSITIES = ("desk", "standing", "physical")


@bp.route("/day/<day>/activity", methods=["POST"])
def add_activity(day):
    """Add school, a shift, a club, a class... to one day or to that weekday every week."""
    try:
        on = date_cls.fromisoformat(day)
    except ValueError:
        return redirect(url_for("plan.week"))
    f = request.form
    hhmm = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    start, end = f.get("start", ""), f.get("end", "")
    if not (hhmm.match(start) and hhmm.match(end)) or end == start:
        flash("Give it a start and an end time, like 09:00 and 15:00.", "error")
        return redirect(url_for("plan.week", week=f.get("week") or None))
    kind = f.get("kind") if f.get("kind") in ACTIVITY_KINDS else "other"
    label = (f.get("label") or "").strip()[:40] or ACTIVITY_KINDS[kind]
    intensity = f.get("intensity") if f.get("intensity") in INTENSITIES else ("physical" if kind == "gym" else "desk")
    try:
        commute = max(0, min(240, int(f.get("commute") or 0)))
    except ValueError:
        commute = 0
    weekly = bool(f.get("weekly"))
    if kind == "work":
        # new work hours replace the usual ones instead of showing up as a second work block
        if weekly:
            execute("UPDATE schedule_days SET work_start = NULL, work_end = NULL WHERE weekday = ?", (on.weekday(),))
        else:
            plans.set_override(on, work_mode="off", work_start=None, work_end=None, commute_min=None, work_kind=None)
    # a night shift (22:00–06:00) is two parts: to midnight, then the early hours of the next day
    nxt = on + timedelta(days=1)
    parts = [(on, start, end)] if end > start else [(on, start, "23:59"), (nxt, "00:00", end)]
    clashes = []
    for day_, a, b in parts:
        clashes += [x["label"] for x in plans.build_days([day_])[day_]["blocks"] if x["start"] < b and a < x["end"]]
        execute("INSERT INTO activities (date, weekday, label, kind, start, end, intensity, commute_min)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (None if weekly else day_.isoformat(), day_.weekday() if weekly else None, label, kind, a, b,
                 intensity, commute))
    if clashes:
        flash(f"Heads up: {label} overlaps {', '.join(dict.fromkeys(clashes))}. Remove one if that's a mistake.", "error")
    when = f"every {on.strftime('%A')}" if weekly else on.strftime("%A")
    overnight = f", running into {nxt.strftime('%A')} morning" if len(parts) > 1 else ""
    return after_day_change(on, f"{label} {start}–{end} added {when}{overnight}")


@bp.route("/activity/<int:activity_id>/remove", methods=["POST"])
def remove_activity(activity_id):
    """Take an activity off: just this date, or (for weekly ones) every week."""
    row = plans.query("SELECT * FROM activities WHERE id = ?", (activity_id,), one=True)
    try:
        on = date_cls.fromisoformat(request.form.get("date", ""))
    except ValueError:
        on = today()
    if row is None:
        return redirect(url_for("plan.week"))
    if row["date"] is None and request.form.get("scope") != "all":
        execute("INSERT OR IGNORE INTO activity_skips (activity_id, date) VALUES (?, ?)", (activity_id, on.isoformat()))
        message = f"{row['label']} skipped on {on.strftime('%A')}"
    else:
        execute("DELETE FROM activities WHERE id = ?", (activity_id,))
        message = f"{row['label']} removed" + (" from every week" if row["date"] is None else "")
    return after_day_change(on, message)

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


def shopping_day():
    """The ?day= being shopped for, if it falls in the selected week from today on."""
    first = selected_week()
    try:
        day = date_cls.fromisoformat(request.values.get("day") or "")
    except ValueError:
        return None
    return day if first <= day <= first + timedelta(days=6) and day >= today() else None


@bp.route("/shopping")
def shopping():
    first = selected_week()
    last = first + timedelta(days=6)
    day = shopping_day()
    if day:
        items, preview = plans.day_shopping(first, day), False
    else:
        items = plans.shopping_list(first)
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
    days = [d for d in (first + timedelta(days=i) for i in range(7)) if d >= today()]
    return render_template("plan/shopping.html", sections=sections, extras=extras, skipped=[f for f in skipped if f],
                           day=day, days=days, today=today(),
                           first=first, preview=preview, has_plan=bool(plans.meals_between(first, last)),
                           is_next=request.args.get("week") == "next", total=total, budget=plans.week_budget(first),
                           count=sum(1 for i in items if not i["checked"]) + sum(1 for e in extras if not e["checked"]))


@bp.route("/shopping/skip/<int:food_id>", methods=["POST"])
def skip(food_id):
    undo = request.form.get("undo") == "1"
    changed = plans.skip_food(selected_week(), food_id, skip=not undo)
    food = store.food(food_id)
    if changed and food:
        flash(f"Not buying {food['name'].lower()}: {changed} meal{'s' if changed != 1 else ''} re-planned without it.", "ok")
    return redirect(url_for("plan.shopping", week=request.values.get("week")))


@bp.route("/shopping/extra", methods=["POST"])
def extra():
    first = selected_week()
    name = (request.form.get("name") or "").strip()[:60]
    if not name:
        flash("Type what you want to buy.", "error")
    else:
        amount = (request.form.get("amount") or "").strip()[:30]
        try:
            cost = max(0, int(float(request.form.get("cost") or 0)))
        except ValueError:
            cost = 0
        guessed = None
        if not cost:
            guessed = plans.guess_item(name, amount)
            if guessed:
                cost, amount = guessed["cost"], amount or guessed["amount"]
        execute("INSERT INTO shopping_extra (week_start, name, amount, est_cost) VALUES (?, ?, ?, ?)",
                      (first.isoformat(), name, amount, cost))
        if guessed:
            flash(f"{name}: guessed about {store_cur()}{cost:,} for {amount}. Change it if you know better.", "ok")
    return redirect(url_for("plan.shopping", week=request.values.get("week")))


@bp.route("/shopping/extra/<int:extra_id>/<action>", methods=["POST"])
def extra_action(extra_id, action):
    if action == "toggle":
        execute("UPDATE shopping_extra SET checked = 1 - checked WHERE id = ?", (extra_id,))
    elif action == "delete":
        execute("DELETE FROM shopping_extra WHERE id = ?", (extra_id,))
    return redirect(url_for("plan.shopping", week=request.values.get("week")))


@bp.route("/shopping/day-bought/<int:food_id>", methods=["POST"])
def day_bought(food_id):
    raw = (request.form.get("price") or "").strip()
    try:
        grams = max(1, int(float(request.form.get("grams") or 0)))
        est = int(float(request.form.get("est") or 0))
    except ValueError:
        abort(400)
    plans.buy_for_day(selected_week(), food_id, grams, int(raw) if raw.isdigit() else est)
    return redirect(url_for("plan.shopping", week=request.values.get("week"), day=request.values.get("day")))


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
