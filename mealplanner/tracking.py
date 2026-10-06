"""Water, weigh-ins and "what can I make now". Plain functions."""
from datetime import timedelta

GLASS_ML = 250
ML_PER_KG = 35


def water_target_ml(weight_kg):
    """About 35 ml per kg of body weight, rounded to whole glasses."""
    return max(4, round(weight_kg * ML_PER_KG / GLASS_ML)) * GLASS_ML


def moving_average(entries, days=7):
    """entries: list of (date, kg) sorted by date. Returns (date, average of the last `days` days) per entry."""
    out = []
    for i, (d, _) in enumerate(entries):
        window = [kg for dd, kg in entries[:i + 1] if (d - dd).days < days]
        out.append((d, round(sum(window) / len(window), 2)))
    return out


def weekly_change(entries):
    """Change in the 7-day average over the last week, or None without enough data."""
    if len(entries) < 2:
        return None
    avg = moving_average(entries)
    last_day, last = avg[-1]
    earlier = [a for d, a in avg if (last_day - d).days >= 7]
    if not earlier:
        return None
    return round(last - earlier[-1], 2)


def chart_points(entries, width=320, height=120, pad=10):
    """SVG polyline points for weights and their trend, scaled to fit the box."""
    if not entries:
        return "", "", None, None
    kgs = [kg for _, kg in entries]
    lo, hi = min(kgs) - 0.5, max(kgs) + 0.5
    first, last = entries[0][0], entries[-1][0]
    span = max(1, (last - first).days)

    def xy(d, kg):
        x = pad + (width - 2 * pad) * (d - first).days / span
        y = pad + (height - 2 * pad) * (hi - kg) / (hi - lo)
        return f"{x:.1f},{y:.1f}"

    raw = " ".join(xy(d, kg) for d, kg in entries)
    trend = " ".join(xy(d, kg) for d, kg in moving_average(entries))
    return raw, trend, round(lo, 1), round(hi, 1)


def makeable_now(recipes, sim, on):
    """Recipes the pantry covers completely for one serving, most expiring food used first.

    sim is a planner.PantrySim. Returns [(recipe, grams_expiring)].
    """
    out = []
    for r in recipes:
        if not r["ingredients"]:
            continue
        factor = 1 / max(1, r["servings"])
        ok, expiring = True, 0.0
        for ing in r["ingredients"]:
            have, missing, exp = sim.check(ing["id"], ing["grams"] * factor, on)
            # condiments under 20 g don't count as missing; most kitchens have them
            if missing > 0 and ing["grams"] * factor > 20:
                ok = False
                break
            expiring += exp
        if ok:
            out.append((r, expiring))
    out.sort(key=lambda x: (-x[1], -x[0]["per_serving"]["protein"]))
    return out


def recent(entries, today, days):
    return [(d, kg) for d, kg in entries if (today - d).days < days]


def days_since(entries, today):
    return (today - entries[-1][0]).days if entries else None


def week_dates(today):
    return [today - timedelta(days=i) for i in range(6, -1, -1)]
