"""Eating-out adjustments, quick picks and workout calorie estimates. Plain functions."""

MIN_PORTION_FACTOR = 0.8

# MET ranges (light effort, all-out effort) from the Compendium of Physical Activities, rounded.
WORKOUT_METS = {
    "weights": (3.5, 6.0),
    "running": (7.0, 11.5),
    "cycling": (5.5, 10.0),
    "walking": (3.0, 5.0),
    "hiit": (6.0, 9.0),
    "swimming": (5.5, 9.5),
    "sports": (5.0, 8.0),
    "other": (3.5, 7.0),
}


def workout_kcal(kind, minutes, effort, weight_kg):
    """Estimated kcal burnt. effort is 1-10 and slides the MET value between its light and hard ends."""
    low, high = WORKOUT_METS.get(kind, WORKOUT_METS["other"])
    effort = max(1, min(10, effort))
    met = low + (high - low) * (effort - 1) / 9
    # MET is kcal per kg per hour including resting; subtract the resting 1 MET to count only the extra
    return round((met - 1) * weight_kg * minutes / 60)


def best_picks(picks, kcal_room, chain=None, limit=8):
    """Quick picks that fit the calories left, most protein per kcal first."""
    options = [p for p in picks if p["kcal"] <= kcal_room and (chain is None or p["chain"] == chain)]
    return sorted(options, key=lambda p: (p["protein"] / max(1, p["kcal"]), -p["kcal"]), reverse=True)[:limit]


def combo_for(picks, kcal_room):
    """A small meal from one chain: best protein per kcal until the room is used up."""
    chosen, kcal, protein, yen = [], 0, 0.0, 0
    for p in best_picks(picks, kcal_room, limit=len(picks)):
        if kcal + p["kcal"] <= kcal_room and p not in chosen:
            chosen.append(p)
            kcal += p["kcal"]
            protein += p["protein"]
            yen += p["yen"]
        if kcal >= kcal_room * 0.85 or len(chosen) >= 3:
            break
    return {"items": chosen, "kcal": kcal, "protein": protein, "yen": yen}


def spread_excess(excess, meals, day_totals, floors):
    """Plan how to absorb extra calories over the coming days.

    meals: editable future meals (dicts with id, date, kind, kcal, portion), in date order.
    day_totals: date -> planned kcal; floors: date -> lowest kcal allowed that day.
    Snacks are dropped first, then meal portions shrink (never below MIN_PORTION_FACTOR of the plan).
    Returns (actions, left_over) where actions are ("drop", id) or ("scale", id, factor).
    """
    actions = []
    totals = dict(day_totals)
    left = excess
    for m in meals:
        if left <= 0:
            break
        if m["kind"] == "snack" and totals[m["date"]] - m["kcal"] >= floors[m["date"]]:
            actions.append(("drop", m["id"]))
            totals[m["date"]] -= m["kcal"]
            left -= m["kcal"]
    for m in meals:
        if left <= 0:
            break
        if m["kind"] not in ("cook", "nocook") or not m["kcal"]:
            continue
        room_day = totals[m["date"]] - floors[m["date"]]
        cut = min(left, m["kcal"] * (1 - MIN_PORTION_FACTOR), max(0, room_day))
        if cut <= 1:
            continue
        actions.append(("scale", m["id"], round(1 - cut / m["kcal"], 3)))
        totals[m["date"]] -= cut
        left -= cut
    return actions, max(0, round(left))
