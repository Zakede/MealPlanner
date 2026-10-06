"""Weekly budget math. Plain functions, amounts in yen."""
from datetime import timedelta


# Which weekday a week starts on (0 = Monday). The app swaps this for one that reads the settings,
# so a week starts on the meal prep day; plain callers and tests get Monday.
week_start_of = lambda: 0  # noqa: E731


def week_bounds(day, week_start=None):
    """Return (first, last) date of the week containing `day`. week_start 0 = Monday."""
    if week_start is None:
        week_start = week_start_of()
    offset = (day.weekday() - week_start) % 7
    first = day - timedelta(days=offset)
    return first, first + timedelta(days=6)


def week_dates(first):
    return [first + timedelta(days=i) for i in range(7)]


def reserved_eat_out(slots, used, per_slot):
    """Money held back for eat-out slots not used yet."""
    return max(0, slots - used) * per_slot


def grocery_cap(weekly_budget, spent, reserved):
    """What the planner may still spend on groceries and konbini this week."""
    return max(0, weekly_budget - spent - reserved)


def status(weekly_budget, spent, planned, reserved=0):
    """Numbers for the budget bar.

    spent: money already spent this week; planned: shopping still to buy;
    reserved: held back for eat-out slots.
    """
    remaining = weekly_budget - spent
    after_plan = remaining - planned - reserved
    return {
        "budget": weekly_budget,
        "spent": round(spent),
        "planned": round(planned),
        "reserved": round(reserved),
        "remaining": round(remaining),
        "after_plan": round(after_plan),
        "over": after_plan < 0,
        "spent_pct": min(100, round(spent / weekly_budget * 100)) if weekly_budget else 100,
        "planned_pct": min(100, round((spent + planned) / weekly_budget * 100)) if weekly_budget else 100,
    }
