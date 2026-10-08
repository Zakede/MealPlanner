"""Snack stash: snacks bought (from receipts or by hand) wait in the pantry; eating one logs it.

A snack's "pack" is the food's piece_g (one bag, one bar). The week's count is what was logged from here.
"""
from datetime import timedelta

from . import budget
from .db import get_db, query
from .logbook import log_food

DEFAULT_PACK_G = 50


def stash():
    """Snacks still in the pantry, fullest first."""
    rows = query("""SELECT p.id, p.quantity, p.price_paid, p.added_on, f.name, f.kcal, f.protein, f.carbs, f.fat, f.piece_g
                    FROM pantry_items p JOIN foods f ON f.id = p.food_id
                    WHERE f.category = 'snack' AND p.quantity > 0 ORDER BY p.added_on DESC, p.id DESC""")
    out = []
    for r in rows:
        r = dict(r)
        pack = r["piece_g"] or min(r["quantity"], DEFAULT_PACK_G)
        r["pack_g"] = round(pack)
        r["packs"] = r["quantity"] / pack if pack else 0
        r["pack_kcal"] = round(r["kcal"] * pack / 100)
        out.append(r)
    return out


def eat(item_id, share, on):
    """Eat `share` of one pack from a stash item. Returns the logged entry, or None if it's gone."""
    row = query("""SELECT p.*, f.name, f.kcal, f.protein, f.carbs, f.fat, f.piece_g
                   FROM pantry_items p JOIN foods f ON f.id = p.food_id WHERE p.id = ?""", (item_id,), one=True)
    if not row or row["quantity"] <= 0:
        return None
    pack = row["piece_g"] or min(row["quantity"], DEFAULT_PACK_G)
    grams = min(row["quantity"], pack * max(0.1, min(share, 1.0)))
    k = grams / 100
    label = row["name"] if share >= 1 else f"{row['name']} (half)" if share >= 0.5 else f"{row['name']} (a bit)"
    # yen stays 0: the snack was already paid for when it was bought
    notes = log_food(on, label, round(row["kcal"] * k), round(row["protein"] * k, 1), round(row["carbs"] * k, 1),
                     round(row["fat"] * k, 1), 0, slot="snack", source="snack")
    db = get_db()
    left = row["quantity"] - grams
    if left < 1:
        db.execute("DELETE FROM pantry_items WHERE id = ?", (item_id,))
    else:
        db.execute("UPDATE pantry_items SET quantity = ? WHERE id = ?", (round(left, 1), item_id))
    db.commit()
    return {"name": label, "kcal": round(row["kcal"] * k), "left": max(0.0, left / pack if pack else 0), "notes": notes}


def week(on):
    """This week's snacks: count, kcal, per-day counts (Mon..Sun) and the entries, newest first."""
    first, last = budget.week_bounds(on)
    rows = [dict(r) for r in query("""SELECT * FROM food_log WHERE source = 'snack' AND date BETWEEN ? AND ?
                                      ORDER BY date DESC, id DESC""", (first.isoformat(), last.isoformat()))]
    days = []
    for i in range(7):
        d = first + timedelta(days=i)
        hits = [r for r in rows if r["date"] == d.isoformat()]
        days.append({"date": d, "count": len(hits), "kcal": sum(r["kcal"] for r in hits)})
    prev_first = first - timedelta(days=7)
    prev = query("""SELECT COUNT(*) AS n, COALESCE(SUM(kcal), 0) AS kcal FROM food_log
                    WHERE source = 'snack' AND date BETWEEN ? AND ?""",
                 (prev_first.isoformat(), (first - timedelta(days=1)).isoformat()), one=True)
    return {"count": len(rows), "kcal": sum(r["kcal"] for r in rows), "days": days, "entries": rows,
            "today": sum(1 for r in rows if r["date"] == on.isoformat()),
            "last_week": prev["n"], "last_week_kcal": prev["kcal"]}
