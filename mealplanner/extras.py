"""Eating-out adjustments, quick picks and workout calorie estimates. Plain functions."""

MIN_PORTION_FACTOR = 0.8

# key: (label, icon, group, MET at light effort, MET all-out), METs from the Compendium of Physical
# Activities, rounded.
WORKOUTS = {
    "weights": ("Weights", "dumbbell", "Gym", 3.5, 6.0),
    "calisthenics": ("Bodyweight", "dumbbell", "Gym", 3.8, 8.0),
    "hiit": ("HIIT", "flame", "Gym", 6.0, 9.0),
    "elliptical": ("Elliptical", "run", "Gym", 5.0, 7.5),
    "rowing": ("Rowing", "run", "Gym", 4.8, 8.5),
    "stairs": ("Stair climber", "run", "Gym", 4.0, 9.0),
    "running": ("Running", "run", "Cardio", 7.0, 11.5),
    "walking": ("Walking", "walk", "Cardio", 3.0, 5.0),
    "hiking": ("Hiking", "walk", "Cardio", 5.3, 7.8),
    "cycling": ("Cycling", "bolt", "Cardio", 5.5, 10.0),
    "swimming": ("Swimming", "drop", "Cardio", 5.5, 9.5),
    "jump_rope": ("Jump rope", "bolt", "Cardio", 8.8, 12.3),
    "dance": ("Dance", "star", "Fun", 4.5, 7.8),
    "boxing": ("Boxing", "flame", "Fun", 5.5, 12.8),
    "martial_arts": ("Martial arts", "flame", "Fun", 5.3, 10.3),
    "climbing": ("Climbing", "hardhat", "Fun", 5.8, 8.0),
    "skating": ("Skating", "bolt", "Fun", 5.0, 9.0),
    "yoga": ("Yoga", "leaf", "Calm", 2.5, 4.0),
    "pilates": ("Pilates", "leaf", "Calm", 3.0, 4.5),
    "stretching": ("Stretching", "feather", "Calm", 2.3, 2.8),
    "soccer": ("Football", "globe", "Sports", 7.0, 10.0),
    "basketball": ("Basketball", "globe", "Sports", 6.0, 8.0),
    "tennis": ("Tennis", "globe", "Sports", 5.0, 8.0),
    "badminton": ("Badminton", "globe", "Sports", 4.5, 7.0),
    "volleyball": ("Volleyball", "globe", "Sports", 3.0, 6.0),
    "sports": ("Other sport", "globe", "Sports", 5.0, 8.0),
    "other": ("Something else", "spark", "Sports", 3.5, 7.0),
}
WORKOUT_METS = {k: (v[3], v[4]) for k, v in WORKOUTS.items()}

# quick ideas by how much time you have: (minutes, kind, effort, what to do)
WORKOUT_IDEAS = [
    (10, "jump_rope", 7, "10 rounds: 30 s skipping, 30 s rest"),
    (10, "calisthenics", 6, "3 rounds: 10 squats, 10 push-ups, 20 s plank"),
    (15, "stretching", 3, "Hips, hamstrings and shoulders, 1 minute each"),
    (20, "walking", 5, "A brisk walk, fast enough that talking is a little hard"),
    (20, "hiit", 8, "8 rounds: 40 s burpees or mountain climbers, 20 s rest"),
    (30, "yoga", 4, "A beginner flow video, 30 minutes"),
    (30, "cycling", 5, "Ride somewhere instead of the train"),
    (45, "weights", 6, "Full body: squats, rows, presses, 3 sets of 8-10"),
    (60, "hiking", 5, "A hill or park trail with snacks"),
]


def label(kind):
    return WORKOUTS.get(kind, WORKOUTS["other"])[0]


def weekly_status(sessions_done, goal, days_since_last):
    """A one-line nudge for the workouts page."""
    if goal and sessions_done >= goal:
        return "Weekly goal done. Anything extra is a bonus; rest counts too."
    if days_since_last is None:
        return "Nothing logged yet. Even a 20-minute walk counts."
    if days_since_last >= 3:
        return f"{days_since_last} days since your last one. A short session today keeps the habit going."
    left = max(0, (goal or 0) - sessions_done)
    return f"{left} more this week to hit your goal." if left else "Nice rhythm. Keep it up."


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
