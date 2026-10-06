"""Quantity, macro and cost math for pantry items and recipes. No DB access."""

MACROS = ("kcal", "protein", "carbs", "fat")


def to_grams(quantity, unit, piece_g=None):
    """Convert a pantry quantity to grams. ml counts as grams (close enough for food)."""
    if unit in ("g", "ml"):
        return float(quantity)
    if unit == "pcs":
        if not piece_g:
            raise ValueError("piece weight unknown for this food")
        return float(quantity) * piece_g
    raise ValueError(f"unknown unit {unit!r}")


def from_grams(grams, unit, piece_g=None):
    if unit == "pcs":
        if not piece_g:
            raise ValueError("piece weight unknown for this food")
        return grams / piece_g
    return grams


def price_per_100g(price_paid, grams):
    if not grams or grams <= 0 or price_paid is None:
        return None
    return price_paid / grams * 100


def macros_for(grams, food):
    """Macros for a weight of a food whose values are per 100 g."""
    factor = grams / 100
    return {m: food[m] * factor for m in MACROS}


def recipe_totals(ingredients):
    """ingredients: iterable of dicts with grams, kcal, protein, carbs, fat, price_per_100g.

    Returns whole-recipe macros, cost, and the names of ingredients with no price.
    """
    totals = {m: 0.0 for m in MACROS}
    cost = 0.0
    unpriced = []
    for ing in ingredients:
        for m, v in macros_for(ing["grams"], ing).items():
            totals[m] += v
        price = ing.get("price_per_100g")
        if price is None:
            unpriced.append(ing.get("name", "?"))
        else:
            cost += ing["grams"] / 100 * price
    totals["cost"] = cost
    totals["unpriced"] = unpriced
    return totals


def per_serving(totals, servings):
    servings = max(1, servings)
    out = {k: totals[k] / servings for k in (*MACROS, "cost")}
    out["unpriced"] = totals.get("unpriced", [])
    return out


def scale(values, factor):
    return {k: v * factor for k, v in values.items() if isinstance(v, (int, float))}


def protein_per_100kcal(protein, kcal):
    return protein / kcal * 100 if kcal else 0.0


def round_macros(values):
    return {
        "kcal": round(values.get("kcal", 0)),
        "protein": round(values.get("protein", 0), 1),
        "carbs": round(values.get("carbs", 0), 1),
        "fat": round(values.get("fat", 0), 1),
        "cost": round(values.get("cost", 0)),
    }
