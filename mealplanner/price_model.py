"""Learns your real food prices from receipts and purchases.

A small hierarchical (empirical Bayes) model in log space. Every observed price becomes a ratio to
the catalogue's reference price. Recent purchases count more (weights halve every HALF_LIFE days).
Three levels are learned, each shrunk toward the level above it when data is thin:

    your overall price level  <- starts at the area/shop factor from settings
      └ one level per food category (meat, veg, dairy, ...)
          └ one level per food

So a single chicken receipt moves chicken a lot, meat a little, and everything else slightly, and a
food you've never bought still gets a better estimate than the catalogue alone. Plain Python, no deps.
"""
import math
from datetime import date

HALF_LIFE_DAYS = 60
K_GLOBAL = 8.0    # how many "receipts" the settings-based prior is worth
K_CATEGORY = 2.0  # how strongly a category leans on your overall level
K_FOOD = 0.5      # how strongly a food leans on its category


def weight(recorded_on, today):
    age = max(0, (today - date.fromisoformat(recorded_on)).days)
    return 0.5 ** (age / HALF_LIFE_DAYS)


def fit(foods, observations, prior_factor, today):
    """foods: {food_id: {"base": local reference price per 100 g, "category": str}}
    observations: iterable of (food_id, price_per_100g, recorded_on)
    prior_factor: area x shop multiplier from settings (1.0 = catalogue as is)

    Returns {"global": factor, "categories": {cat: factor}, "foods": {food_id: estimate dict}}.
    """
    by_food = {}
    for food_id, price, recorded_on in observations:
        f = foods.get(food_id)
        if not f or not f["base"] or not price or price <= 0:
            continue
        by_food.setdefault(food_id, []).append((math.log(price / f["base"]), weight(recorded_on, today), recorded_on, price))

    prior = math.log(prior_factor) if prior_factor > 0 else 0.0
    sw = sum(w for obs in by_food.values() for _, w, _, _ in obs)
    swr = sum(w * r for obs in by_food.values() for r, w, _, _ in obs)
    mu_global = (swr + K_GLOBAL * prior) / (sw + K_GLOBAL)

    cat_sums = {}
    for food_id, obs in by_food.items():
        cat = foods[food_id]["category"] or "other"
        s = cat_sums.setdefault(cat, [0.0, 0.0])
        s[0] += sum(w for _, w, _, _ in obs)
        s[1] += sum(w * r for r, w, _, _ in obs)
    mu_cat = {cat: (swr_c + K_CATEGORY * mu_global) / (sw_c + K_CATEGORY) for cat, (sw_c, swr_c) in cat_sums.items()}

    estimates = {}
    for food_id, f in foods.items():
        cat = f["category"] or "other"
        level = mu_cat.get(cat, mu_global)
        obs = by_food.get(food_id, [])
        n_eff = sum(w for _, w, _, _ in obs)
        mu = (sum(w * r for r, w, _, _ in obs) + K_FOOD * level) / (n_eff + K_FOOD) if obs else level
        estimates[food_id] = {
            "price": f["base"] * math.exp(mu) if f["base"] else None,
            "n": len(obs),
            "n_eff": round(n_eff, 2),
            "source": "learned" if n_eff >= 0.3 else ("category" if cat in mu_cat else "estimate"),
            "trend": trend(obs),
        }
    return {"global": math.exp(mu_global), "categories": {c: math.exp(m) for c, m in mu_cat.items()},
            "foods": estimates, "observations": sum(len(o) for o in by_food.values())}


def trend(obs):
    """Price change per 30 days (as a fraction) from a weighted line through log prices, or None."""
    if len(obs) < 3:
        return None
    xs = [date.fromisoformat(d).toordinal() for _, _, d, _ in obs]
    ys = [math.log(p) for _, _, _, p in obs]
    ws = [w for _, w, _, _ in obs]
    sw = sum(ws)
    mx = sum(w * x for w, x in zip(ws, xs)) / sw
    my = sum(w * y for w, y in zip(ws, ys)) / sw
    var = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs))
    if var == 0:
        return None
    slope = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys)) / var
    return math.exp(slope * 30) - 1
