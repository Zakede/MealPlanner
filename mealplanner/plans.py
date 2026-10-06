"""Loading, saving and changing plans in the database. Planning decisions live in planner.py."""
import json
from datetime import date, datetime, timedelta

from flask import current_app

from . import budget, planner, store, today as get_today
from .db import get_db, query
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
    return groceries + eaten_out


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
    flexible = s.get("schedule_mode") == "flexible"
    prep = set()
    if flexible and dates:
        count = max(0, min(len(dates), s.get("prep_days") or 0))
        # spread prep days out so each batch covers the days after it
        prep = {dates[round(i * len(dates) / count)] for i in range(count)} if count else set()
    days = {}
    for d in dates:
        day = dict(sched[d.weekday()])
        if flexible:
            day.update(work_start=None, work_end=None, commute_min=0, gym=0, away=0,
                       effort="full" if d in prep else "low")
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
        day["prep"] = d in prep or (o is not None and o["effort"] == "full")
        days[d] = day
    return days


OVERRIDE_KEYS = ("effort", "gym", "away", "work_mode", "work_start", "work_end", "commute_min", "note")


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
    now = now_minutes() if on == get_today() else -1
    days = build_days([on])
    rows = [dict(r) for r in query("SELECT * FROM plan_meals WHERE date = ? AND status IN ('draft', 'approved')",
                                   (on.isoformat(),))]
    clear = [r for r in rows if not r["eat_time"] or minutes(r["eat_time"]) >= now]
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
        "prefs": {r["recipe_id"]: r["status"] for r in query("SELECT * FROM recipe_prefs")},
        "budget_cap": cap,
        "eat_out_slots_left": max(0, s["eat_out_slots"] - used - planned_eat_out),
        "existing": existing,
        "exclude": exclude or {},
        "skip": skip or set(),
    }


def past_slots(dates):
    """Today's slots whose meal time has already gone by are not planned."""
    today = get_today()
    if today not in dates:
        return set()
    day = build_days([today])[today]
    now = now_minutes()
    return {(today, slot) for slot in planner.MEAL_SLOTS + ("snack",)
            if minutes(planner.eat_time(day, slot)) < now}


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
        kcal, protein = day_targets(targets, day["gym"], gym_days, s["sex"])
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


def shopping_needs(first, statuses=("approved",)):
    """What planned meals still need beyond the pantry: food_id -> {grams, price}."""
    last = first + timedelta(days=6)
    today = get_today()
    sim = planner.PantrySim(pantry_lots())
    need = {}
    for m in meals_between(max(first, today), last):
        if m["status"] not in statuses or m["kind"] not in ("cook", "nocook", "snack") or not m["recipe"]:
            continue
        for ing, grams in planner.scaled_ingredients(m["recipe"], m["cook_portions"]):
            missing = sim.take(ing["id"], grams, m["date"])
            if missing > 0.5:
                entry = need.setdefault(ing["id"], {"grams": 0.0, "price": ing.get("price_per_100g") or 0,
                                                    "name": ing["name"], "piece_g": ing.get("piece_g")})
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


def shopping_preview(first):
    """The list a draft plan would need, without saving anything."""
    need = shopping_needs(first, statuses=("draft", "approved"))
    rows = [{"id": None, "food_id": fid, "name": e["name"], "piece_g": e["piece_g"], "grams": round(e["grams"]),
             "est_cost": round(e["grams"] / 100 * e["price"]), "checked": 0} for fid, e in need.items()]
    return sorted(rows, key=lambda r: r["name"])


def shopping_list(first):
    rows = query("""SELECT s.*, f.name, f.piece_g FROM shopping_list s JOIN foods f ON f.id = s.food_id
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
