"""Turns a weekday's schedule into what the planner can use: time available and allowed effort."""
from datetime import datetime

EFFORT_MAX_ACTIVE = {"none": 5, "low": 15, "full": 120}
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def minutes(hhmm):
    if not hhmm:
        return None
    t = datetime.strptime(hhmm, "%H:%M")
    return t.hour * 60 + t.minute


def hhmm(total):
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def works(day):
    return bool(day.get("work_start") and day.get("work_end")) or bool(day.get("blocks"))


def blocks(day):
    """Busy stretches of the day as (leave, back) minutes, commute included, in time order."""
    if day.get("blocks") is not None:
        raw = [(b["start"], b["end"], b.get("commute") or 0) for b in day["blocks"]]
    elif day.get("work_start") and day.get("work_end"):
        raw = [(day["work_start"], day["work_end"], day.get("commute_min") or 0)]
    else:
        raw = []
    return sorted((minutes(a) - c, minutes(b) + c) for a, b, c in raw if minutes(b) > minutes(a))


# how far a meal can slide to dodge a busy stretch, and how long after getting home a moved dinner is
SHIFT_MAX = {"lunch": 120, "dinner": 150}
HOME_BEFORE = {"lunch": 15, "dinner": 30}
LATEST_DINNER = 22 * 60 + 30
EARLIEST_BREAKFAST = 4 * 60


def fit_meal_times(day):
    """Move meal times around the day's activities. Changes `day` and returns notes like
    "Dinner 20:20, after Gym". A meal deep inside a long stretch stays put and is packed instead."""
    stretches = sorted(((minutes(b["start"]) - (b.get("commute") or 0), minutes(b["end"]) + (b.get("commute") or 0),
                         b["label"]) for b in day.get("blocks") or [] if minutes(b["end"]) > minutes(b["start"])))
    notes = []
    if not stretches:
        return notes

    def covering(t):
        return next(((a, b, label) for a, b, label in stretches if a <= t < b), None)

    bt = minutes(day["breakfast_time"])
    hit = covering(bt)
    if hit and hit[0] - 20 >= EARLIEST_BREAKFAST:
        bt = hit[0] - 20
        day["breakfast_time"] = hhmm(bt)
        day["wake"] = hhmm(min(minutes(day["wake"]) or 7 * 60, bt - 20))
        notes.append(f"Breakfast {day['breakfast_time']}, before {hit[2]}")
    for slot in ("lunch", "dinner"):
        t = minutes(day[f"{slot}_time"])
        hit = covering(t)
        if not hit:
            continue
        # follow on from anything that starts right after (gym after work)
        end = hit[1]
        for a, b, _ in stretches:
            if a <= end + 15 and b > end:
                end = b
        moved = end + HOME_BEFORE[slot]
        if moved - t <= SHIFT_MAX[slot] and (slot == "lunch" or moved <= LATEST_DINNER):
            day[f"{slot}_time"] = hhmm(moved)
            notes.append(f"{slot.capitalize()} {day[slot + '_time']}, after {hit[2]}")
    return notes


def slot_limits(day):
    """Max cooking minutes per slot, and whether the slot is eaten away from home."""
    wake = minutes(day["wake"]) or 7 * 60
    effort_cap = EFFORT_MAX_ACTIVE[day["effort"]]
    busy_at = blocks(day)
    lunch, dinner = minutes(day["lunch_time"]), minutes(day["dinner_time"])

    def inside(t):
        return any(a < t < b for a, b in busy_at)

    morning = [a for a, _ in busy_at if a < lunch]
    breakfast_time = max(0, morning[0] - wake - 10) if morning else 45
    lunch_at_work = inside(lunch) or any(a <= lunch <= b for a, b in busy_at)
    if any(a <= dinner < b for a, b in busy_at):
        dinner_time, dinner_away = 0, True
    else:
        back = max([b for _, b in busy_at if b <= dinner] or [dinner - 120])
        dinner_time, dinner_away = max(0, min(120, dinner - back)), False

    limits = {
        "breakfast": {"max_total": min(breakfast_time, 30), "max_active": min(effort_cap, 15), "away": False},
        "lunch": {"max_total": 0 if lunch_at_work else 60,
                  "max_active": 0 if lunch_at_work else effort_cap, "away": lunch_at_work},
        "dinner": {"max_total": dinner_time, "max_active": 0 if dinner_away else effort_cap, "away": dinner_away},
        "snack": {"max_total": 15, "max_active": 5, "away": False},
    }
    if day["away"]:
        for slot in ("lunch", "dinner"):
            limits[slot] = {"max_total": 0, "max_active": 0, "away": True}
    return limits


def busy(day):
    """Busy means low/no effort, or an evening with under 45 minutes to cook."""
    return day["effort"] != "full" or slot_limits(day)["dinner"]["max_total"] < 45
