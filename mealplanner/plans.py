"""Loading, saving and changing plans in the database. Planning decisions live in planner.py."""
import json
from datetime import date, datetime, timedelta

from flask import current_app

from . import budget, food_rules, planner, store, today as get_today
from .db import execute, get_db, query
from .nutrition import day_targets
from .schedule import minutes
from .taste import is_favorite, recipe_score, tag_affinity

EDITABLE = ("draft", "approved")
SLOT_ORDER = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}


def now_minutes():
    override = current_app.config.get("NOW")
    if override:
        return minutes(override)
    if current_app.config.get("TODAY"):
        return 0
    t = datetime.now()
    return t.hour * 60 + t.minute


def current_week(on=None):
    return budget.week_bounds(on or get_today())


def _d(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def meals_between(first, last):
    recipes = {r["id"]: r for r in store.recipes()}
    rows = query("SELECT * FROM plan_meals WHERE date BETWEEN ? AND ?", (first.isoformat(), last.isoformat()))
    meals = []
    for row in rows:
        m = dict(row)
        m["date"] = _d(m["date"])
        m["recipe"] = recipes.get(m["recipe_id"])
        meals.append(m)
    meals.sort(key=lambda m: (m["date"], SLOT_ORDER[m["slot"]], m["id"]))
    return meals


def spent_between(first, last):
    groceries = query("SELECT COALESCE(SUM(price_paid), 0) s FROM pantry_items WHERE added_on BETWEEN ? AND ?",
                      (first.isoformat(), last.isoformat()), one=True)["s"]
    eaten_out = query("SELECT COALESCE(SUM(yen), 0) s FROM eating_out_log WHERE date BETWEEN ? AND ?",
                      (first.isoformat(), last.isoformat()), one=True)["s"]
    snacks = query("SELECT COALESCE(SUM(yen), 0) s FROM food_log WHERE date BETWEEN ? AND ?",
                   (first.isoformat(), last.isoformat()), one=True)["s"]
    return groceries + eaten_out + snacks


def eat_out_used(first, last):
    return query("SELECT COUNT(*) c FROM eating_out_log WHERE planned = 1 AND date BETWEEN ? AND ?",
                 (first.isoformat(), last.isoformat()), one=True)["c"]


def reserved_money(s, first, last):
    return budget.reserved_eat_out(s["eat_out_slots"], eat_out_used(first, last), s["eat_out_budget_yen"])


def week_budget(first):
    s = store.settings()
    last = first + timedelta(days=6)
    shopping = query("SELECT COALESCE(SUM(est_cost), 0) s FROM shopping_list WHERE week_start = ? AND checked = 0",
                     (first.isoformat(),), one=True)["s"]
    shopping += query("SELECT COALESCE(SUM(est_cost), 0) s FROM shopping_extra WHERE week_start = ? AND checked = 0",
                      (first.isoformat(),), one=True)["s"]
    konbini = sum(m["buy_cost"] for m in meals_between(first, last)
                  if m["kind"] == "konbini" and m["status"] in EDITABLE)
    return budget.status(s["weekly_budget_yen"], spent_between(first, last), shopping + konbini,
                         reserved_money(s, first, last))


def pantry_lots():
    lots = []
    for item in store.pantry_items(get_today()):
        if item["grams"]:
            lots.append((item["food_id"], item["grams"], _d(item["expiry"]) if item["expiry"] else None))
    return lots


def taste_context(recipes, s):
    ratings = query("SELECT recipe_id, stars, tags FROM ratings ORDER BY rated_on")
    stars, feedback = {}, {}
    for r in ratings:
        stars.setdefault(r["recipe_id"], []).append(r["stars"])
        feedback.setdefault(r["recipe_id"], []).extend(store.split_list(r["tags"]))
    ingredient_scores = {r["food_id"]: r["score"] for r in query("SELECT * FROM taste_scores")}
    affinity = tag_affinity([(r["recipe_id"], r["stars"]) for r in ratings],
                            {r["id"]: r["tag_list"] for r in recipes})
    base = {
        "flavor_likes": store.split_list(s["flavor_likes"]),
        "cuisines_liked": store.split_list(s["cuisines_liked"]),
        "cuisines_loved": store.split_list(s.get("cuisines_loved")),
        "cuisines_tired": store.split_list(s["cuisines_tired"]),
        "ingredient_scores": ingredient_scores,
        "affinity": affinity,
    }
    taste = {r["id"]: recipe_score(r, dict(base, stars=stars.get(r["id"], []),
                                           feedback_tags=feedback.get(r["id"], [])))
             for r in recipes}
    favorites = {rid for rid, st in stars.items() if is_favorite(st)}
    return taste, favorites, feedback


def boosters():
    rows = query("""SELECT b.*, f.name, f.allergens, f.kcal * b.grams / 100 AS kcal,
                           f.protein * b.grams / 100 AS protein
                    FROM flavor_boosters b JOIN foods f ON f.id = b.food_id""")
    out = []
    for r in rows:
        b = dict(r)
        b["tag_list"] = store.split_list(b["tags"])
        b["allergens"] = store.split_list(b["allergens"])
        out.append(b)
    return out


def weekday_schedule():
    return {r["weekday"]: dict(r) for r in query("SELECT * FROM schedule_days")}


def build_days(dates, s=None):
    """Schedule for each date: weekday pattern, flexible-mode defaults, then one-off overrides."""
    s = s or store.settings()
    sched = weekday_schedule()
    overrides = {_d(r["date"]): dict(r) for r in query("SELECT * FROM day_overrides")}
    acts = [dict(r) for r in query("SELECT * FROM activities")]
    skips = {(r["activity_id"], r["date"]) for r in query("SELECT * FROM activity_skips")}
    flexible = s.get("schedule_mode") == "flexible"
    prep = set()
    if flexible and dates:
        count = max(0, min(len(dates), s.get("prep_days") or 0))
        # spread prep days out so each batch covers the days after it
        prep = {dates[round(i * len(dates) / count)] for i in range(count)} if count else set()
    # chosen meal prep days (e.g. Sunday) are a big cook in either mode
    prep_weekdays = {int(x) for x in store.split_list(s.get("prep_weekdays")) if x.isdigit()}
    days = {}
    for d in dates:
        day = dict(sched[d.weekday()])
        if flexible:
            # hours change week to week: only the cooking rhythm is defaulted. Work or gym you put in the
            # Schedule (or on a day) still counts, so editing it always shows up.
            day.update(effort="full" if d in prep else "low")
        if d.weekday() in prep_weekdays:
            day["effort"] = "full"
        o = overrides.get(d)
        if o:
            for key in ("effort", "gym", "away"):
                if o[key] is not None:
                    day[key] = o[key]
            if o.get("work_mode") == "off":
                day.update(work_start=None, work_end=None, commute_min=0)
            elif o.get("work_mode") == "work" and o.get("work_start") and o.get("work_end"):
                day.update(work_start=o["work_start"], work_end=o["work_end"],
                           commute_min=o["commute_min"] if o.get("commute_min") is not None else day["commute_min"])
            day["note"] = o.get("note") or ""
        else:
            day["note"] = ""
        # everything that takes you out of the kitchen: usual work plus any added activities
        blocks = []
        if day.get("work_start") and day.get("work_end"):
            day["work_hours"] = max(0, (minutes(day["work_end"]) - minutes(day["work_start"])) / 60)
            day["work_job"] = (o or {}).get("work_kind") or s.get("job") or "desk"
            blocks.append({"id": None, "label": "Work", "kind": "work", "start": day["work_start"],
                           "end": day["work_end"], "intensity": day["work_job"], "commute": day.get("commute_min") or 0,
                           "hours": day["work_hours"], "weekly": not (o and o.get("work_mode") == "work")})
        else:
            day["work_hours"], day["work_job"] = 0, None
        for a in acts:
            if (a["date"] == d.isoformat() or (a["weekday"] == d.weekday() and not a["date"]))                     and (a["id"], d.isoformat()) not in skips:
                blocks.append({"id": a["id"], "label": a["label"], "kind": a["kind"], "start": a["start"], "end": a["end"],
                               "intensity": a["intensity"], "commute": a["commute_min"], "weekly": a["date"] is None,
                               "hours": max(0, (minutes(a["end"]) - minutes(a["start"])) / 60)})
                if a["kind"] == "gym":
                    day["gym"] = 1
        day["blocks"] = sorted(blocks, key=lambda b: b["start"])
        day["prep"] = d in prep or (o is not None and o["effort"] == "full")
        # a meal prep day cooks for the days up to the next one, unless that date was changed by hand
        day["prep_day"] = d.weekday() in prep_weekdays and not (o is not None and o["effort"] not in (None, "full"))
        day["prep"] = day["prep"] or day["prep_day"]
        days[d] = day
    return days


OVERRIDE_KEYS = ("effort", "gym", "away", "work_mode", "work_start", "work_end", "commute_min", "note", "work_kind")


work_of = planner.work_of


def saved_activities(limit=8):
    """Activities you've added before, newest first and without repeats, to add again in one tap."""
    out, seen = [], set()
    for r in query("SELECT * FROM activities ORDER BY id DESC"):
        key = (r["label"].lower(), r["kind"], r["start"], r["end"], r["intensity"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"label": r["label"], "kind": r["kind"], "start": r["start"], "end": r["end"],
                    "intensity": r["intensity"], "commute": r["commute_min"]})
        if len(out) >= limit:
            break
    return out


def set_override(on, **values):
    """Change parts of one date's override. None clears that part."""
    row = query("SELECT * FROM day_overrides WHERE date = ?", (on.isoformat(),), one=True)
    current = {k: (dict(row).get(k) if row else None) for k in OVERRIDE_KEYS}
    current.update(values)
    db = get_db()
    if all(current[k] in (None, "") for k in OVERRIDE_KEYS):
        db.execute("DELETE FROM day_overrides WHERE date = ?", (on.isoformat(),))
    else:
        cols = ", ".join(OVERRIDE_KEYS)
        db.execute(f"INSERT OR REPLACE INTO day_overrides (date, {cols}) VALUES (?, {', '.join('?' * len(OVERRIDE_KEYS))})",
                   (on.isoformat(), *[current[k] for k in OVERRIDE_KEYS]))
    db.commit()


def override(on):
    row = query("SELECT * FROM day_overrides WHERE date = ?", (on.isoformat(),), one=True)
    return dict(row) if row else {}


def replan_rest_of_day(on):
    """Plan one day's remaining meals again (after e.g. "gym today"), leaving the other days alone."""
    first, last = budget.week_bounds(on)
    # everything not eaten yet is fair game, whatever the time
    clear = [dict(r) for r in query("SELECT * FROM plan_meals WHERE date = ? AND status IN ('draft', 'approved')",
                                    (on.isoformat(),))]
    for r in clear:
        clear += [dict(x) for x in query("SELECT * FROM plan_meals WHERE cook_group = ? AND status IN ('draft', 'approved')",
                                         (r["id"],))]
    ids = {r["id"] for r in clear}
    if ids:
        get_db().execute(f"DELETE FROM plan_meals WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))
        get_db().commit()
    dates = [d for d in budget.week_dates(first) if d >= on]
    filled = {(m["date"], m["slot"]) for m in meals_between(first, last)}
    cleared = {(_d(r["date"]), r["slot"]) for r in clear}
    all_slots = {(d, slot) for d in dates for slot in planner.MEAL_SLOTS + ("snack",)}
    skip = (all_slots - filled - cleared) | past_slots(dates)
    ctx = load_context(first, last, skip=skip)
    save_meals(planner.plan(ctx, dates))
    save_plan_days([on])
    return len(ids)


def load_context(first, last, exclude=None, skip=None):
    s = store.settings()
    today = get_today()
    recipes = store.recipes()
    by_id = {r["id"]: r for r in recipes}
    existing = meals_between(first, last)
    taste, favorites, feedback = taste_context(recipes, s)

    history = {}
    for row in query("SELECT recipe_id, date FROM plan_meals WHERE recipe_id IS NOT NULL AND date BETWEEN ? AND ?",
                     ((first - timedelta(days=14)).isoformat(), last.isoformat())):
        history.setdefault(row["recipe_id"], []).append(_d(row["date"]))

    leftovers = []
    for row in query("SELECT * FROM leftovers WHERE portions > 0 AND safe_until >= ?", (today.isoformat(),)):
        lo = dict(row)
        lo["safe_until"] = _d(lo["safe_until"])
        recipe = by_id.get(lo["recipe_id"])
        lo["portable"] = bool(recipe and recipe["portable"])
        leftovers.append(lo)

    used = eat_out_used(first, last)
    planned_eat_out = sum(1 for m in existing if m["kind"] == "eat_out" and m["status"] in EDITABLE)
    cap = budget.grocery_cap(s["weekly_budget_yen"], spent_between(first, last), reserved_money(s, first, last))

    return {
        "today": today,
        "settings": s,
        "targets": store.targets(s),
        "recipes": recipes,
        "schedule": weekday_schedule(),
        "days": build_days([first + timedelta(days=i) for i in range((last - first).days + 1)], s),
        "appliances": set(store.split_list(s.get("appliances"))),
        "pantry_lots": pantry_lots(),
        "fridge_leftovers": leftovers,
        "history": history,
        "taste": taste,
        "favorites": favorites,
        "feedback": feedback,
        "boosters": boosters(),
        "quick_picks": [dict(r) for r in query("SELECT * FROM quick_picks")],
        "allergies": store.split_list(s["allergies"]),
        "dislikes": store.split_list(s["dislikes"]),
        "spice_tolerance": s["spice_tolerance"],
        "flavor_likes": store.split_list(s["flavor_likes"]),
        "diet": s.get("diet") or "any",
        "avoid": store.split_list(s.get("avoid")),
        "food_rules": food_rules.load(s),
        "skip_foods": {r["food_id"] for r in query("SELECT food_id FROM shopping_skip WHERE week_start = ?",
                                                   (first.isoformat(),))},
        "prefs": {r["recipe_id"]: r["status"] for r in query("SELECT * FROM recipe_prefs")},
        "budget_cap": cap,
        "eat_out_slots_left": max(0, s["eat_out_slots"] - used - planned_eat_out),
        "existing": existing,
        "exclude": exclude or {},
        "skip": skip or set(),
    }


def past_slots(dates):
    """Slots never get dropped for the clock: meal times are only suggestions, so planning at 7 am or
    7 pm still fills the whole day. Kept as a hook so callers stay simple."""
    return set()


def save_meals(meals):
    db = get_db()
    cook_ids = {}
    for m in sorted(meals, key=lambda m: m["kind"] == "leftover"):
        group = cook_ids.get(m.get("cook_key")) if m["kind"] == "leftover" else None
        cur = db.execute(
            """INSERT INTO plan_meals (date, slot, kind, recipe_id, portion, cook_portions, cook_group, leftover_id,
                   booster_id, title, kcal, protein, carbs, fat, cost, buy_cost, status, eat_time, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (m["date"].isoformat(), m["slot"], m["kind"], m.get("recipe_id"), m["portion"], m["cook_portions"],
             group, m.get("leftover_id"), m.get("booster_id"), m["title"], round(m["kcal"], 1),
             round(m["protein"], 1), round(m["carbs"], 1), round(m["fat"], 1), round(m["cost"]),
             round(m["buy_cost"]), m.get("status", "draft"), m.get("eat_time"), m.get("note", "")),
        )
        if m["kind"] in ("cook", "nocook") and m.get("cook_key"):
            cook_ids[m["cook_key"]] = cur.lastrowid
    db.commit()


def save_plan_days(dates):
    s = store.settings()
    targets = store.targets(s)
    days = build_days(sorted(dates), s)
    gym_days = sum(1 for d in weekday_schedule().values() if d["gym"]) if s.get("schedule_mode") != "flexible"         else max(1, s.get("training_days") or 0)
    db = get_db()
    for d in dates:
        day = days[d]
        kcal, protein = day_targets(targets, day["gym"], gym_days, s["sex"], work=work_of(day, s))
        db.execute("""INSERT INTO plan_days (date, kcal_target, protein_target, gym, effort, away)
                      VALUES (?, ?, ?, ?, ?, ?)
                      ON CONFLICT(date) DO UPDATE SET kcal_target = excluded.kcal_target,
                        protein_target = excluded.protein_target, gym = excluded.gym,
                        effort = excluded.effort, away = excluded.away""",
                   (d.isoformat(), kcal, protein, day["gym"], day["effort"], day["away"]))
    db.commit()


def generate_week(first):
    """Throw away the editable part of the week from today on, and plan it again as a draft."""
    if store.targets() is None:
        raise ValueError("Set your age and sex in settings before planning.")
    today = get_today()
    last = first + timedelta(days=6)
    dates = [d for d in budget.week_dates(first) if d >= today]
    if not dates:
        return []
    db = get_db()
    db.execute("DELETE FROM plan_meals WHERE date BETWEEN ? AND ? AND status IN ('draft', 'approved')",
               (dates[0].isoformat(), last.isoformat()))
    db.execute("DELETE FROM shopping_list WHERE week_start = ?", (first.isoformat(),))
    db.commit()
    ctx = load_context(first, last, skip=past_slots(dates))
    meals = planner.plan(ctx, dates)
    save_meals(meals)
    save_plan_days(dates)
    return meals


def replan_from(on):
    """A day changed: plan it and the rest of its week again. Cooked and eaten meals stay put."""
    if store.targets() is None:
        raise ValueError("Set your age and sex in settings before planning.")
    first, last = budget.week_bounds(on)
    start = max(on, get_today())
    dates = [d for d in budget.week_dates(first) if d >= start]
    if not dates:
        return []
    db = get_db()
    had_list = bool(query("SELECT 1 FROM shopping_list WHERE week_start = ? LIMIT 1", (first.isoformat(),)))
    was_approved = bool(query("SELECT 1 FROM plan_meals WHERE status = 'approved' AND date BETWEEN ? AND ? LIMIT 1",
                              (first.isoformat(), last.isoformat())))
    db.execute("DELETE FROM plan_meals WHERE date BETWEEN ? AND ? AND status IN ('draft', 'approved')",
               (dates[0].isoformat(), last.isoformat()))
    db.commit()
    ctx = load_context(first, last, skip=past_slots(dates))
    meals = planner.plan(ctx, dates)
    if was_approved:
        for m in meals:
            m["status"] = "approved"   # an approved week stays approved; the list just updates
    save_meals(meals)
    save_plan_days(dates)
    if had_list or was_approved:
        build_shopping_list(first)
    return meals


def dependents(meal_id):
    return [dict(r) for r in query("SELECT * FROM plan_meals WHERE cook_group = ? AND status IN ('draft', 'approved')",
                                   (meal_id,))]


def replace_flagged(first):
    last = first + timedelta(days=6)
    flagged = [dict(r) for r in query(
        "SELECT * FROM plan_meals WHERE replace_flag = 1 AND date BETWEEN ? AND ? AND status IN ('draft', 'approved')",
        (first.isoformat(), last.isoformat()))]
    if not flagged:
        return 0
    exclude, ids, cleared = {}, set(), set()
    for m in flagged:
        for x in [m] + dependents(m["id"]):
            ids.add(x["id"])
            cleared.add((_d(x["date"]), x["slot"]))
            if x["recipe_id"]:
                exclude.setdefault((_d(x["date"]), x["slot"]), set()).add(x["recipe_id"])
    db = get_db()
    db.execute(f"DELETE FROM plan_meals WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))
    db.commit()

    # only the cleared slots get refilled; anything that was already empty stays empty
    filled = {(m["date"], m["slot"]) for m in meals_between(first, last)}
    all_slots = {(d, slot) for d in budget.week_dates(first) for slot in planner.MEAL_SLOTS + ("snack",)}
    skip = (all_slots - filled - cleared) | past_slots(budget.week_dates(first))
    dates = [d for d in budget.week_dates(first) if d >= get_today()]
    ctx = load_context(first, last, exclude=exclude, skip=skip)
    save_meals(planner.plan(ctx, dates))
    return len(flagged)


def approve_week(first):
    replaced = replace_flagged(first)
    last = first + timedelta(days=6)
    db = get_db()
    db.execute("UPDATE plan_meals SET status = 'approved' WHERE status = 'draft' AND date BETWEEN ? AND ?",
               (first.isoformat(), last.isoformat()))
    db.commit()
    build_shopping_list(first)
    return replaced


def shopping_needs(first, statuses=("approved",), only=None):
    """What planned meals still need beyond the pantry: food_id -> {grams, price}. Skipped foods are left out.

    With `only` (a date), just that day's meals count, after earlier days have used up the pantry."""
    last = first + timedelta(days=6)
    today = get_today()
    sim = planner.PantrySim(pantry_lots())
    skipped = skipped_foods(first)
    from .staples import at_home, load as load_staples
    home = at_home(load_staples(store.settings()))
    need = {}
    for m in meals_between(max(first, today), last):
        if m["status"] not in statuses or m["kind"] not in ("cook", "nocook", "snack") or not m["recipe"]:
            continue
        for ing, grams in planner.scaled_ingredients(m["recipe"], m["cook_portions"]):
            missing = sim.take(ing["id"], grams, m["date"])
            if only is not None and m["date"] != only:
                continue
            if missing > 0.5 and ing["id"] not in skipped and ing["name"].lower() not in home:
                entry = need.setdefault(ing["id"], {"grams": 0.0, "price": ing.get("price_per_100g") or 0,
                                                    "name": ing["name"], "piece_g": ing.get("piece_g"),
                                                    "category": ing.get("category") or ""})
                entry["grams"] += missing
    return need


def build_shopping_list(first):
    """Everything approved meals still need, minus what the pantry already has."""
    need = shopping_needs(first)
    db = get_db()
    checked = {r["food_id"] for r in query("SELECT food_id FROM shopping_list WHERE week_start = ? AND checked = 1",
                                           (first.isoformat(),))}
    db.execute("DELETE FROM shopping_list WHERE week_start = ?", (first.isoformat(),))
    for food_id, e in need.items():
        db.execute("INSERT INTO shopping_list (week_start, food_id, grams, est_cost, checked) VALUES (?, ?, ?, ?, ?)",
                   (first.isoformat(), food_id, round(e["grams"]), round(e["grams"] / 100 * e["price"]),
                    1 if food_id in checked else 0))
    db.commit()


def day_shopping(first, day):
    """What one day's meals need (draft or approved), for buying a day at a time."""
    need = shopping_needs(first, statuses=("draft", "approved"), only=day)
    return [{"food_id": fid, "name": e["name"], "grams": round(e["grams"]), "piece_g": e["piece_g"],
             "category": e["category"], "est_cost": round(e["grams"] / 100 * e["price"]), "checked": 0}
            for fid, e in need.items()]


def buy_for_day(first, food_id, grams, price):
    """Put one day's amount in the pantry and take it off the week's list."""
    db = get_db()
    today = get_today().isoformat()
    db.execute("INSERT INTO pantry_items (food_id, quantity, unit, price_paid, location, added_on)"
               " VALUES (?, ?, 'g', ?, 'fridge', ?)", (food_id, grams, price, today))
    if price and grams:
        db.execute("INSERT INTO price_history (food_id, price_per_100g, recorded_on, source) VALUES (?, ?, ?, 'shopping')",
                   (food_id, round(price / grams * 100, 2), today))
    row = query("SELECT * FROM shopping_list WHERE week_start = ? AND food_id = ? AND checked = 0",
                (first.isoformat(), food_id), one=True)
    if row:
        left = row["grams"] - grams
        if left <= 0.5:
            db.execute("UPDATE shopping_list SET checked = 1 WHERE id = ?", (row["id"],))
        else:
            db.execute("UPDATE shopping_list SET grams = ?, est_cost = ? WHERE id = ?",
                       (round(left), round(row["est_cost"] * left / row["grams"]), row["id"]))
    db.commit()


def shopping_preview(first):
    """The list a draft plan would need, without saving anything."""
    need = shopping_needs(first, statuses=("draft", "approved"))
    rows = [{"id": None, "food_id": fid, "name": e["name"], "piece_g": e["piece_g"], "grams": round(e["grams"]),
             "category": e["category"],
             "est_cost": round(e["grams"] / 100 * e["price"]), "checked": 0} for fid, e in need.items()]
    return sorted(rows, key=lambda r: r["name"])


def skipped_foods(first):
    return {r["food_id"] for r in query("SELECT food_id FROM shopping_skip WHERE week_start = ?", (first.isoformat(),))}


def skip_food(first, food_id, skip=True):
    """Not buying a food this week. Meals that needed it are planned again without it.

    Returns how many meals changed.
    """
    db = get_db()
    changed = 0
    if skip:
        db.execute("INSERT OR IGNORE INTO shopping_skip (week_start, food_id) VALUES (?, ?)", (first.isoformat(), food_id))
        db.execute("DELETE FROM shopping_list WHERE week_start = ? AND food_id = ?", (first.isoformat(), food_id))
        db.commit()
        changed = refit_week(first, lambda recipe: any(i["id"] == food_id for i in recipe["ingredients"]))
    else:
        db.execute("DELETE FROM shopping_skip WHERE week_start = ? AND food_id = ?", (first.isoformat(), food_id))
        db.commit()
    if query("SELECT 1 FROM plan_meals WHERE status = 'approved' AND date BETWEEN ? AND ? LIMIT 1",
             (first.isoformat(), (first + timedelta(days=6)).isoformat())):
        build_shopping_list(first)
    return changed


def refit_week(first, wrong):
    """Plan again every meal still to come this week whose recipe `wrong(recipe)` rejects.

    An approved week stays approved: the new meals are approved too and the list follows.
    """
    last = first + timedelta(days=6)
    start = max(first, get_today())
    rows = query("""SELECT * FROM plan_meals WHERE date BETWEEN ? AND ? AND status IN ('draft', 'approved')
                    AND recipe_id IS NOT NULL AND kind != 'leftover'""", (start.isoformat(), last.isoformat()))
    recipes, ids = {}, []
    for m in rows:
        if m["recipe_id"] not in recipes:
            recipes[m["recipe_id"]] = store.recipe(m["recipe_id"])
        r = recipes[m["recipe_id"]]
        if r and wrong(r):
            ids.append(m["id"])
    if not ids:
        return 0
    was_approved = bool(query("SELECT 1 FROM plan_meals WHERE status = 'approved' AND date BETWEEN ? AND ? LIMIT 1",
                              (first.isoformat(), last.isoformat())))
    db = get_db()
    db.execute(f"UPDATE plan_meals SET replace_flag = 1 WHERE id IN ({','.join('?' * len(ids))})", ids)
    db.commit()
    replace_flagged(first)
    if was_approved:
        db.execute("UPDATE plan_meals SET status = 'approved' WHERE status = 'draft' AND date BETWEEN ? AND ?",
                   (first.isoformat(), last.isoformat()))
        db.commit()
        build_shopping_list(first)
    return len(ids)


def refit_for_rules():
    """After the protein rules change: fix this week and next so no meal breaks them."""
    rules = food_rules.load(store.settings())
    first, _ = current_week()
    return sum(refit_week(f, lambda r: food_rules.breaks(r, rules)) for f in (first, first + timedelta(days=7)))


def shopping_extras(first):
    return [dict(r) for r in query("SELECT * FROM shopping_extra WHERE week_start = ? ORDER BY checked, id",
                                   (first.isoformat(),))]


def shopping_list(first):
    rows = query("""SELECT s.*, f.name, f.piece_g, f.category FROM shopping_list s JOIN foods f ON f.id = s.food_id
                    WHERE s.week_start = ? ORDER BY s.checked, f.name""", (first.isoformat(),))
    return [dict(r) for r in rows]


def add_bought_to_pantry(first, item_id, price_paid=None):
    """Move a shopping list item into the pantry at its estimated (or given) price."""
    row = query("""SELECT s.*, f.name FROM shopping_list s JOIN foods f ON f.id = s.food_id WHERE s.id = ?""",
                (item_id,), one=True)
    if not row:
        return
    price = row["est_cost"] if price_paid is None else price_paid
    db = get_db()
    db.execute("INSERT INTO pantry_items (food_id, quantity, unit, price_paid, location, added_on)"
               " VALUES (?, ?, 'g', ?, 'fridge', ?)",
               (row["food_id"], row["grams"], price, get_today().isoformat()))
    if price and row["grams"]:
        db.execute("INSERT INTO price_history (food_id, price_per_100g, recorded_on, source) VALUES (?, ?, ?, 'shopping')",
                   (row["food_id"], round(price / row["grams"] * 100, 2), get_today().isoformat()))
    db.execute("UPDATE shopping_list SET checked = 1 WHERE id = ?", (item_id,))
    db.commit()


def week_has_plan(first):
    last = first + timedelta(days=6)
    return query("SELECT COUNT(*) c FROM plan_meals WHERE date BETWEEN ? AND ? AND date >= ?",
                 (first.isoformat(), last.isoformat(), get_today().isoformat()), one=True)["c"] > 0


def replan_if_planned():
    """Settings or schedule changed: plan the rest of this week again, if there is a plan."""
    first, _ = current_week()
    if store.targets() is not None and week_has_plan(first):
        generate_week(first)
        return True
    return False


def push_back(days):
    """Slide tonight's dinner and everything after it later by `days`. Returns the action id."""
    today = get_today()
    rows = query("SELECT * FROM plan_meals WHERE date >= ? AND status IN ('draft', 'approved')", (today.isoformat(),))
    moved = [r["id"] for r in rows
             if _d(r["date"]) > today or SLOT_ORDER[r["slot"]] >= SLOT_ORDER["dinner"]]
    if not moved:
        return None
    db = get_db()
    marks = ",".join("?" * len(moved))
    db.execute(f"UPDATE plan_meals SET date = date(date, '+{int(days)} day') WHERE id IN ({marks})", tuple(moved))
    cur = db.execute("INSERT INTO plan_actions (created_at, action, payload) VALUES (?, 'push_back', ?)",
                     (datetime.now().isoformat(timespec="seconds"), json.dumps({"ids": moved, "days": int(days)})))
    db.commit()
    shifted = {_d(r["date"]) + timedelta(days=int(days)) for r in rows if r["id"] in moved}
    save_plan_days(sorted(shifted))
    flag_unsafe_leftovers()
    return cur.lastrowid


def undo_last():
    row = query("SELECT * FROM plan_actions WHERE undone = 0 ORDER BY id DESC LIMIT 1", one=True)
    if not row:
        return False
    payload = json.loads(row["payload"])
    if row["action"] == "status":
        for meal_id, status in payload["previous"].items():
            get_db().execute("UPDATE plan_meals SET status = ? WHERE id = ?", (status, int(meal_id)))
    elif row["action"] == "push_back":
        ids = payload["ids"]
        marks = ",".join("?" * len(ids))
        get_db().execute(f"UPDATE plan_meals SET date = date(date, '-{int(payload['days'])} day') "
                         f"WHERE id IN ({marks}) AND status IN ('draft', 'approved')", tuple(ids))
    get_db().execute("UPDATE plan_actions SET undone = 1 WHERE id = ?", (row["id"],))
    get_db().commit()
    flag_unsafe_leftovers()
    return True


def flag_unsafe_leftovers():
    """Leftover meals that now fall after their fridge-safe date get a warning note."""
    db = get_db()
    for m in query("""SELECT pm.id, pm.date, pm.note, l.safe_until, c.date AS cook_date, r.fridge_days
                      FROM plan_meals pm
                      LEFT JOIN leftovers l ON l.id = pm.leftover_id
                      LEFT JOIN plan_meals c ON c.id = pm.cook_group
                      LEFT JOIN recipes r ON r.id = pm.recipe_id
                      WHERE pm.kind = 'leftover' AND pm.status IN ('draft', 'approved')"""):
        limit = _d(m["safe_until"]) if m["safe_until"] else (
            _d(m["cook_date"]) + timedelta(days=m["fridge_days"] or 3) if m["cook_date"] else None)
        warn = "Past its fridge-safe date: freeze it or skip"
        note = m["note"].replace(" · " + warn, "").replace(warn, "")
        if limit and _d(m["date"]) > limit:
            note = (note + " · " if note else "") + warn
        db.execute("UPDATE plan_meals SET note = ? WHERE id = ?", (note, m["id"]))
    db.commit()


def set_replace(meal_id, flag):
    get_db().execute("UPDATE plan_meals SET replace_flag = ? WHERE id = ? AND status IN ('draft', 'approved')",
                     (1 if flag else 0, meal_id))
    get_db().commit()


def day_summaries(first):
    last = first + timedelta(days=6)
    meals = meals_between(first, last)
    targets = {r["date"]: dict(r) for r in query("SELECT * FROM plan_days WHERE date BETWEEN ? AND ?",
                                                 (first.isoformat(), last.isoformat()))}
    days = []
    for d in budget.week_dates(first):
        ms = [m for m in meals if m["date"] == d]
        t = targets.get(d.isoformat())
        days.append({
            "date": d, "meals": ms, "target": t,
            "kcal": round(sum(m["kcal"] for m in ms if m["status"] != "skipped")),
            "protein": round(sum(m["protein"] for m in ms if m["status"] != "skipped")),
        })
    return days


def never_again(recipe_id):
    """Block a recipe and swap it out of every upcoming meal."""
    store.set_recipe_pref(recipe_id, "never")
    today = get_today()
    rows = query("SELECT id, date FROM plan_meals WHERE recipe_id = ? AND date >= ? AND status IN ('draft', 'approved')"
                 " AND kind != 'leftover'", (recipe_id, today.isoformat()))
    for r in rows:
        set_replace(r["id"], True)
    weeks = {budget.week_bounds(_d(r["date"]))[0] for r in rows}
    for first in sorted(weeks):
        replace_flagged(first)
    return len(rows)


def add_meal(on, slot, recipe_id):
    """Put a chosen recipe into a slot, sized to that slot's share of the day."""
    recipe = store.recipe(recipe_id)
    if not recipe:
        raise ValueError("recipe not found")
    s = store.settings()
    targets = store.targets(s)
    if targets is None:
        raise ValueError("Set your age and sex first.")
    row = query("SELECT * FROM plan_days WHERE date = ?", (on.isoformat(),), one=True)
    if not row:
        save_plan_days([on])
        row = query("SELECT * FROM plan_days WHERE date = ?", (on.isoformat(),), one=True)
    if slot == "snack":
        target = s["snack_kcal"]
    else:
        target = (row["kcal_target"] - s["snack_kcal"]) * planner.SLOT_SHARE[slot]
    portion = planner.best_portion(recipe["per_serving"]["kcal"], target)
    sched = {r["weekday"]: dict(r) for r in query("SELECT * FROM schedule_days")}
    meal = {"date": on, "slot": slot, "kind": "snack" if slot == "snack" else ("cook" if recipe["active_min"] else "nocook"),
            "recipe_id": recipe_id, "portion": portion, "cook_portions": portion, "title": recipe["name"],
            "cost": recipe["per_serving"]["cost"] * portion, "buy_cost": 0, "note": "Added by you",
            "eat_time": planner.eat_time(sched[on.weekday()], slot),
            **planner.macros_for(recipe, portion)}
    save_meals([meal])
    first = budget.week_bounds(on)[0]
    if query("SELECT 1 FROM shopping_list WHERE week_start = ? LIMIT 1", (first.isoformat(),)):
        get_db().execute("UPDATE plan_meals SET status = 'approved' WHERE date = ? AND slot = ? AND recipe_id = ?"
                         " AND status = 'draft'", (on.isoformat(), slot, recipe_id))
        get_db().commit()
        build_shopping_list(first)


# grams in a usual pack, for guessing a price when you don't say how much
PACK_GRAMS = {"poultry": 300, "meat": 300, "fish": 250, "seafood": 200, "egg": 600, "dairy": 400, "soy": 300,
              "legume": 400, "grain": 500, "veg": 200, "fruit": 300, "sauce": 200, "fat": 200, "snack": 150}


def _grams(amount, piece_g):
    """'500g', '1.5 kg', '2 pcs', '3個' -> grams, or None."""
    import re
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(kg|g|ml|l|pcs?|pieces?|個|本|枚|packs?|袋)?\s*$", (amount or "").lower())
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2) or "g"
    if unit == "kg" or unit == "l":
        return n * 1000
    if unit in ("g", "ml"):
        return n
    return n * (piece_g or 100)


def guess_item(name, amount=""):
    """A price for something typed into the shopping list: a food you already have, or a known kind of food."""
    from .food_guess import guess
    from .pricing import factor
    lower = name.lower().strip()
    food = store.food_by_name(name)
    if not food:
        matches = [f for f in store.foods() if f["name"].lower() in lower or lower in f["name"].lower()]
        food = max(matches, key=lambda f: len(f["name"])) if matches else None
    if food and food.get("current_price"):
        per100, category, piece = food["current_price"], food.get("category") or "", food.get("piece_g")
    else:
        g = guess(name)
        if not g or not g.get("price_jpy"):
            return None
        per100, category, piece = g["price_jpy"] * factor(store.settings()), g["category"], None
    grams = _grams(amount, piece)
    label = amount
    if grams is None:
        grams = PACK_GRAMS.get(category, 200)
        label = f"about {grams} g"
    return {"cost": max(1, round(per100 * grams / 100)), "amount": label}


def add_simple_meal(on, slot, title, kcal, protein=0, carbs=0, fat=0, cost=0, kind="konbini", note=""):
    """Put a ready-made thing (a konbini item, a snack, something typed in) into a slot. No recipe needed."""
    if slot not in ("breakfast", "lunch", "dinner", "snack"):
        raise ValueError("pick a meal")
    first = budget.week_bounds(on)[0]
    approved = bool(query("SELECT 1 FROM shopping_list WHERE week_start = ? LIMIT 1", (first.isoformat(),)))
    sched = {r["weekday"]: dict(r) for r in query("SELECT * FROM schedule_days")}
    save_meals([{"date": on, "slot": slot, "kind": kind, "recipe_id": None, "portion": 1, "cook_portions": 1,
                 "title": title[:80], "kcal": kcal, "protein": protein, "carbs": carbs, "fat": fat,
                 "cost": cost, "buy_cost": cost, "note": note or "Added by you",
                 "eat_time": planner.eat_time(sched[on.weekday()], slot),
                 "status": "approved" if approved else "draft"}])
    if not query("SELECT 1 FROM plan_days WHERE date = ?", (on.isoformat(),), one=True) and store.targets():
        save_plan_days([on])
