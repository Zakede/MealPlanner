"""What happens after cooking or eating: pantry deduction, leftovers, status changes."""
import json
import re
from datetime import datetime, timedelta

from . import store, today as get_today
from .costing import from_grams, to_grams
from .db import get_db, query
from .planner import scaled_ingredients

FREEZER_DAYS = 30
STEP_MINUTES = re.compile(r"(\d+)(?:\s*-\s*(\d+))?\s*min", re.IGNORECASE)


def step_timer(step):
    """Minutes mentioned in a step ("8-10 minutes" -> 10), or None."""
    m = STEP_MINUTES.search(step)
    if not m:
        return None
    return int(m.group(2) or m.group(1))


def deduct(food_id, grams, on):
    """Take grams of a food out of the pantry, soonest expiry first. Returns grams not found."""
    db = get_db()
    rows = query("""SELECT p.*, f.piece_g FROM pantry_items p JOIN foods f ON f.id = p.food_id
                    WHERE p.food_id = ? ORDER BY p.expiry IS NULL, p.expiry, p.id""", (food_id,))
    need = grams
    for row in rows:
        if need <= 0:
            break
        if row["expiry"] and row["expiry"] < on.isoformat():
            continue  # expired stock is not cooked with
        try:
            have = to_grams(row["quantity"], row["unit"], row["piece_g"])
        except ValueError:
            continue
        used = min(have, need)
        need -= used
        left = have - used
        if left <= 0.5:
            db.execute("DELETE FROM pantry_items WHERE id = ?", (row["id"],))
        else:
            qty = from_grams(left, row["unit"], row["piece_g"])
            # keep the original paid price on the row; spending is counted when it was bought
            db.execute("UPDATE pantry_items SET quantity = ? WHERE id = ?", (round(qty, 2), row["id"]))
    db.commit()
    return max(0.0, need)


def deduct_recipe(recipe, portions, on):
    missing = []
    for ing, grams in scaled_ingredients(recipe, portions):
        short = deduct(ing["id"], grams, on)
        if short > 1:
            missing.append((ing["name"], round(short)))
    return missing


def _record(action, payload):
    get_db().execute("INSERT INTO plan_actions (created_at, action, payload) VALUES (?, ?, ?)",
                     (datetime.now().isoformat(timespec="seconds"), action, json.dumps(payload)))


def finish_cooking(meal, freeze=False):
    """Mark a cook meal as cooked, take ingredients from the pantry, and store the extra portions."""
    recipe = store.recipe(meal["recipe_id"])
    on = get_today()
    cook_portions = meal["cook_portions"] or meal["portion"]
    missing = deduct_recipe(recipe, cook_portions, on)
    db = get_db()
    db.execute("UPDATE plan_meals SET status = 'cooked', replace_flag = 0 WHERE id = ?", (meal["id"],))

    extra = round(cook_portions - meal["portion"], 2)
    leftover_id = None
    if extra > 0.01:
        s = recipe["per_serving"]

        def store_portions(portions, frozen):
            days = FREEZER_DAYS if frozen else recipe["fridge_days"]
            return db.execute(
                """INSERT INTO leftovers (recipe_id, cook_meal_id, title, portions, kcal, protein, carbs, fat,
                       cooked_on, safe_until, location) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (recipe["id"], meal["id"], recipe["name"], portions, s["kcal"], s["protein"], s["carbs"], s["fat"],
                 on.isoformat(), (on + timedelta(days=days)).isoformat(), "freezer" if frozen else "fridge"),
            ).lastrowid

        # meal-prep boxes planned past the fridge life go straight in the freezer
        boxes = [dict(r) for r in query("SELECT id, date, portion FROM plan_meals WHERE cook_group = ?"
                                        " AND status IN ('draft', 'approved')", (meal["id"],))]
        fridge_until = on + timedelta(days=recipe["fridge_days"])
        late = [b for b in boxes if datetime.fromisoformat(b["date"]).date() > fridge_until]
        late_portions = round(min(extra, sum(b["portion"] for b in late)), 2)
        if late and not freeze and late_portions < extra - 0.01:
            leftover_id = store_portions(round(extra - late_portions, 2), False)
            frozen_id = store_portions(late_portions, True)
            db.execute("UPDATE plan_meals SET leftover_id = ? WHERE cook_group = ?", (leftover_id, meal["id"]))
            db.execute(f"UPDATE plan_meals SET leftover_id = ? WHERE id IN ({','.join('?' * len(late))})",
                       (frozen_id, *[b["id"] for b in late]))
        else:
            leftover_id = store_portions(extra, freeze or bool(late))
            # planned leftover meals from this cook now draw from the real leftover
            db.execute("UPDATE plan_meals SET leftover_id = ? WHERE cook_group = ?", (leftover_id, meal["id"]))
    db.commit()
    return {"missing": missing, "leftover_portions": extra, "leftover_id": leftover_id}


def eat(meal):
    """Mark a no-cook meal, snack or leftover as eaten."""
    on = get_today()
    db = get_db()
    missing = []
    if meal["kind"] == "leftover":
        lo_id = meal["leftover_id"]
        if lo_id:
            db.execute("UPDATE leftovers SET portions = MAX(0, portions - ?) WHERE id = ?", (meal["portion"], lo_id))
    elif meal["recipe_id"]:
        missing = deduct_recipe(store.recipe(meal["recipe_id"]), meal["cook_portions"] or meal["portion"], on)
    db.execute("UPDATE plan_meals SET status = 'eaten', replace_flag = 0 WHERE id = ?", (meal["id"],))
    db.commit()
    return missing


def skip(meal):
    """Skip a meal. Leftover meals that depended on it are skipped too. Can be undone."""
    db = get_db()
    ids = [meal["id"]] + [r["id"] for r in query(
        "SELECT id FROM plan_meals WHERE cook_group = ? AND status IN ('draft', 'approved')", (meal["id"],))]
    previous = {str(r["id"]): r["status"] for r in query(
        f"SELECT id, status FROM plan_meals WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))}
    db.execute(f"UPDATE plan_meals SET status = 'skipped' WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))
    _record("status", {"previous": previous})
    db.commit()
    return len(ids)


EXPIRED_GRACE_DAYS = 2   # past its date: a "toss it" reminder for 2 days, then it's cleared away


def leftovers():
    on = get_today()
    db = get_db()
    db.execute("UPDATE leftovers SET portions = 0 WHERE portions > 0 AND safe_until < ?",
               ((on - timedelta(days=EXPIRED_GRACE_DAYS)).isoformat(),))
    db.commit()
    rows = query("SELECT * FROM leftovers WHERE portions > 0 ORDER BY safe_until")
    out = []
    on = get_today()
    for r in rows:
        lo = dict(r)
        lo["days_left"] = (datetime.fromisoformat(lo["safe_until"]).date() - on).days
        out.append(lo)
    return out


def freeze_leftover(leftover_id):
    on = get_today()
    get_db().execute("UPDATE leftovers SET location = 'freezer', safe_until = ? WHERE id = ? AND location = 'fridge'",
                     ((on + timedelta(days=FREEZER_DAYS)).isoformat(), leftover_id))
    get_db().commit()


def discard_leftover(leftover_id):
    get_db().execute("UPDATE leftovers SET portions = 0 WHERE id = ?", (leftover_id,))
    get_db().commit()
