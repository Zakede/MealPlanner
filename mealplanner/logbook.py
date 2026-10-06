"""Eating out, spending and workouts: the database side."""
from datetime import timedelta

from . import budget, plans, store
from .costing import to_grams
from .db import get_db, query
from .extras import spread_excess
from .nutrition import CALORIE_FLOOR
from .plans import EDITABLE, _d


def log_eat_out(on, slot, place, item, kcal, protein, yen):
    """Record a meal eaten out and rebalance the rest of the week. Returns a list of messages."""
    first, last = budget.week_bounds(on)
    db = get_db()
    notes = []

    planned_here = [dict(r) for r in query(
        "SELECT * FROM plan_meals WHERE date = ? AND slot = ? AND status IN ('draft', 'approved')",
        (on.isoformat(), slot))]
    reserved_here = next((m for m in planned_here if m["kind"] == "eat_out"), None)
    replaced_kcal = sum(m["kcal"] for m in planned_here)

    uses_slot = reserved_here is not None
    if not uses_slot:
        # spend one of the week's reserved slots if any is still open later on
        future = query("""SELECT * FROM plan_meals WHERE kind = 'eat_out' AND status IN ('draft', 'approved')
                          AND date BETWEEN ? AND ? AND NOT (date = ? AND slot = ?) ORDER BY date DESC LIMIT 1""",
                       (first.isoformat(), last.isoformat(), on.isoformat(), slot), one=True)
        if future:
            uses_slot = True
            db.execute("UPDATE plan_meals SET replace_flag = 1 WHERE id = ?", (future["id"],))
            notes.append(f"Used the eat-out slot from {_d(future['date']).strftime('%a')}; that meal gets planned now.")

    for m in planned_here:
        db.execute("UPDATE plan_meals SET status = 'eaten_out', replace_flag = 0 WHERE id = ?", (m["id"],))
        # leftover meals that relied on this cook need a new plan
        db.execute("UPDATE plan_meals SET replace_flag = 1 WHERE cook_group = ? AND status IN ('draft', 'approved')",
                   (m["id"],))
    db.execute("INSERT INTO eating_out_log (date, slot, place, item, kcal, protein, yen, planned)"
               " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (on.isoformat(), slot, place, item, kcal, protein, yen, 1 if uses_slot else 0))
    db.commit()
    if query("SELECT 1 FROM plan_meals WHERE replace_flag = 1 AND date BETWEEN ? AND ? LIMIT 1",
             (first.isoformat(), last.isoformat())):
        plans.replace_flagged(first)

    excess = kcal - (replaced_kcal if planned_here else 0)
    if excess > 50:
        notes += rebalance(on, last, excess)
    return notes


def rebalance(after, last, excess):
    s = store.settings()
    floor = CALORIE_FLOOR.get(s["sex"], 1200)
    meals = [m for m in plans.meals_between(after + timedelta(days=1), last) if m["status"] in EDITABLE]
    if not meals:
        return [f"{round(excess)} kcal over today. Nothing left this week to balance it."]
    totals = {}
    for m in meals:
        totals[m["date"]] = totals.get(m["date"], 0) + m["kcal"]
    actions, left = spread_excess(excess, meals, totals, {d: floor for d in totals})
    db = get_db()
    dropped = scaled = 0
    by_id = {m["id"]: m for m in meals}
    for action in actions:
        m = by_id[action[1]]
        if action[0] == "drop":
            db.execute("UPDATE plan_meals SET status = 'skipped', note = 'Dropped to balance eating out' WHERE id = ?",
                       (m["id"],))
            dropped += 1
        else:
            f = action[2]
            new_portion = round(m["portion"] * f, 2)
            cook_portions = max(new_portion, round(m["cook_portions"] - m["portion"] * (1 - f), 2))
            db.execute("""UPDATE plan_meals SET portion = ?, cook_portions = ?, kcal = kcal * ?, protein = protein * ?,
                          carbs = carbs * ?, fat = fat * ? WHERE id = ?""",
                       (new_portion, cook_portions, f, f, f, f, m["id"]))
            scaled += 1
    db.commit()
    msg = [f"Balanced {round(excess - left)} extra kcal: dropped {dropped} snack{'s' if dropped != 1 else ''}, "
           f"trimmed {scaled} meal{'s' if scaled != 1 else ''} a little."]
    if left:
        msg.append(f"{left} kcal couldn't be balanced without going under your minimum. That's fine for one week.")
    first = budget.week_bounds(after)[0]
    if query("SELECT 1 FROM shopping_list WHERE week_start = ? LIMIT 1", (first.isoformat(),)):
        plans.build_shopping_list(first)
        msg.append("Shopping list updated.")
    return msg


def spending(first):
    """What was bought this week, estimated vs paid, and what the week will cost in total."""
    last = first + timedelta(days=6)
    rows = query("""SELECT p.*, f.name, f.piece_g, f.price_per_100g AS ref_price FROM pantry_items p
                    JOIN foods f ON f.id = p.food_id WHERE p.added_on BETWEEN ? AND ? ORDER BY p.added_on DESC""",
                 (first.isoformat(), last.isoformat()))
    bought = []
    for r in rows:
        item = dict(r)
        try:
            grams = to_grams(item["quantity"], item["unit"], item["piece_g"])
        except ValueError:
            grams = None
        item["estimate"] = round(grams / 100 * item["ref_price"]) if grams and item["ref_price"] else None
        bought.append(item)
    meals_out = [dict(r) for r in query("SELECT * FROM eating_out_log WHERE date BETWEEN ? AND ? ORDER BY date DESC",
                                        (first.isoformat(), last.isoformat()))]
    status = plans.week_budget(first)
    groceries = sum(i["price_paid"] or 0 for i in bought)
    estimated = sum(i["estimate"] or 0 for i in bought if i["price_paid"])
    history = []
    for k in range(1, 5):
        wk = first - timedelta(days=7 * k)
        history.append({"week": wk, "spent": plans.spent_between(wk, wk + timedelta(days=6))})
    return {
        "bought": bought,
        "meals_out": meals_out,
        "groceries": groceries,
        "estimated": estimated,
        "eat_out": sum(m["yen"] for m in meals_out),
        "expected_total": status["spent"] + status["planned"] + status["reserved"],
        "status": status,
        "history": history,
    }


def price_changes(limit=8):
    """Foods whose latest price differs most from the one before it."""
    out = []
    for f in store.foods():
        rows = query("SELECT price_per_100g FROM price_history WHERE food_id = ? ORDER BY recorded_on DESC, id DESC LIMIT 2",
                     (f["id"],))
        if len(rows) == 2 and rows[1]["price_per_100g"]:
            change = (rows[0]["price_per_100g"] - rows[1]["price_per_100g"]) / rows[1]["price_per_100g"]
            if abs(change) >= 0.05:
                out.append({"name": f["name"], "now": rows[0]["price_per_100g"], "before": rows[1]["price_per_100g"],
                            "change": change})
    return sorted(out, key=lambda x: -abs(x["change"]))[:limit]


def workouts_between(first, last):
    return [dict(r) for r in query("SELECT * FROM workouts WHERE date BETWEEN ? AND ? ORDER BY date DESC, id DESC",
                                   (first.isoformat(), last.isoformat()))]


def log_food(on, name, kcal, protein=0, carbs=0, fat=0, yen=0, slot="snack", source="manual", time=None):
    """Record something eaten outside the plan. Returns messages about what changed."""
    db = get_db()
    db.execute("INSERT INTO food_log (date, time, slot, name, kcal, protein, carbs, fat, yen, source)"
               " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (on.isoformat(), time, slot, name[:80], int(kcal), protein, carbs, fat, int(yen), source))
    notes = []
    # an unplanned snack stands in for the planned one
    if slot == "snack":
        planned = query("SELECT id, title FROM plan_meals WHERE date = ? AND slot = 'snack'"
                        " AND status IN ('draft', 'approved')", (on.isoformat(),), one=True)
        if planned:
            db.execute("UPDATE plan_meals SET status = 'skipped', note = 'Swapped for something you ate' WHERE id = ?",
                       (planned["id"],))
            notes.append(f"Skipped the planned {planned['title']}.")
    db.commit()

    # over today's target? spread the rest over the coming days like an unplanned meal out
    row = query("SELECT kcal_target FROM plan_days WHERE date = ?", (on.isoformat(),), one=True)
    if row:
        planned_today = sum(m["kcal"] for m in plans.meals_between(on, on)
                            if m["status"] not in ("skipped",))
        extra = sum(r["kcal"] for r in query("SELECT kcal FROM food_log WHERE date = ?", (on.isoformat(),)))
        out = sum(r["kcal"] for r in query("SELECT kcal FROM eating_out_log WHERE date = ?", (on.isoformat(),)))
        over = planned_today + extra + out - row["kcal_target"]
        new_over = min(over, int(kcal)) if over > 0 else 0
        if new_over > 50:
            first, last = budget.week_bounds(on)
            notes += rebalance(on, last, new_over)
    return notes


def food_today(on):
    return [dict(r) for r in query("SELECT * FROM food_log WHERE date = ? ORDER BY id", (on.isoformat(),))]
