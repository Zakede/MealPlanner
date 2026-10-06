"""Numbers for the Progress page: what you ate, spent, drank and weighed over a stretch of days."""
from datetime import timedelta

from .db import query

EATEN = ("cooked", "eaten")


def _by_day(sql, first, last):
    return {r["date"]: r for r in query(sql, (first.isoformat(), last.isoformat()))}


def daily(first, last, s, targets, water_target):
    """One row per day from first to last: kcal, protein, money, water, and whether goals were hit."""
    meals = _by_day("""SELECT date, SUM(kcal) kcal, SUM(protein) protein, COUNT(*) n FROM plan_meals
                       WHERE status IN ('cooked', 'eaten') AND date BETWEEN ? AND ? GROUP BY date""", first, last)
    logged = _by_day("""SELECT date, SUM(kcal) kcal, SUM(protein) protein, SUM(yen) yen FROM food_log
                        WHERE date BETWEEN ? AND ? GROUP BY date""", first, last)
    out = _by_day("""SELECT date, SUM(kcal) kcal, SUM(protein) protein, SUM(yen) yen FROM eating_out_log
                     WHERE date BETWEEN ? AND ? GROUP BY date""", first, last)
    shop = _by_day("""SELECT added_on AS date, SUM(COALESCE(price_paid, 0)) yen FROM pantry_items
                      WHERE added_on BETWEEN ? AND ? GROUP BY added_on""", first, last)
    water = _by_day("SELECT date, ml FROM water_log WHERE date BETWEEN ? AND ?", first, last)
    kcal_goal = targets.kcal if targets else None
    protein_goal = targets.protein_g if targets else None
    days = []
    d = first
    while d <= last:
        k = d.isoformat()
        kcal = sum((src[k]["kcal"] or 0) for src in (meals, logged, out) if k in src)
        protein = sum((src[k]["protein"] or 0) for src in (meals, logged, out) if k in src)
        spent = sum((src[k]["yen"] or 0) for src in (logged, out, shop) if k in src)
        ml = water[k]["ml"] if k in water else 0
        tracked = kcal > 0
        days.append({
            "date": d, "kcal": round(kcal), "protein": round(protein), "spent": round(spent), "water": ml,
            "cooked": meals[k]["n"] if k in meals else 0, "tracked": tracked,
            "protein_hit": bool(tracked and protein_goal and protein >= protein_goal * 0.9),
            "kcal_ok": bool(tracked and kcal_goal and kcal <= kcal_goal * 1.05),
            "water_hit": ml >= water_target,
        })
        d += timedelta(days=1)
    return days


def streak(days, key):
    """Days in a row (ending today, or yesterday if today isn't done yet) where `key` was true."""
    n = 0
    for i, day in enumerate(reversed(days)):
        if day[key]:
            n += 1
        elif i == 0:
            continue  # today still in progress
        else:
            break
    return n


def summary(days):
    tracked = [d for d in days if d["tracked"]]
    return {
        "spent": sum(d["spent"] for d in days),
        "avg_kcal": round(sum(d["kcal"] for d in tracked) / len(tracked)) if tracked else None,
        "avg_protein": round(sum(d["protein"] for d in tracked) / len(tracked)) if tracked else None,
        "cooked": sum(d["cooked"] for d in days),
        "tracked_days": len(tracked),
        "water_days": sum(1 for d in days if d["water_hit"]),
        "protein_days": sum(1 for d in tracked if d["protein_hit"]),
        "on_target_days": sum(1 for d in tracked if d["kcal_ok"]),
    }
