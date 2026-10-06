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
    return bool(day.get("work_start") and day.get("work_end"))


def slot_limits(day):
    """Max cooking minutes per slot, and whether the slot is eaten away from home."""
    wake = minutes(day["wake"]) or 7 * 60
    effort_cap = EFFORT_MAX_ACTIVE[day["effort"]]

    if works(day):
        leave = minutes(day["work_start"]) - (day["commute_min"] or 0)
        home = minutes(day["work_end"]) + (day["commute_min"] or 0)
        breakfast_time = max(0, leave - wake - 10)
        lunch_at_work = minutes(day["work_start"]) <= minutes(day["lunch_time"]) <= minutes(day["work_end"])
        dinner_time = max(0, minutes(day["dinner_time"]) - home)
    else:
        breakfast_time, lunch_at_work, dinner_time = 45, False, 120

    limits = {
        "breakfast": {"max_total": min(breakfast_time, 30), "max_active": min(effort_cap, 15), "away": False},
        "lunch": {"max_total": 0 if lunch_at_work else 60,
                  "max_active": 0 if lunch_at_work else effort_cap, "away": lunch_at_work},
        "dinner": {"max_total": dinner_time, "max_active": effort_cap, "away": False},
        "snack": {"max_total": 15, "max_active": 5, "away": False},
    }
    if day["away"]:
        for slot in ("lunch", "dinner"):
            limits[slot] = {"max_total": 0, "max_active": 0, "away": True}
    return limits


def busy(day):
    """Busy means low/no effort, or an evening with under 45 minutes to cook."""
    return day["effort"] != "full" or slot_limits(day)["dinner"]["max_total"] < 45
